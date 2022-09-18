# timstaxtools
# https://github.com/ttimtucker/timstaxtools.git

host:
=====
Amazon EC2 Ubuntu VM, free tier
Opened ports 80, 443, 22

references:
===========
https://www.digitalocean.com/community/tutorials/how-to-create-a-self-signed-ssl-certificate-for-nginx-in-ubuntu-16-04
https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-18-04

sqlite3 DB:
=============
>>> c=sqlite3.connect("hub.db")
>>> c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
[('globs',), ('hubdata',), ('flash',)]

>>> c.execute("SELECT sql FROM sqlite_schema WHERE name='globs'").fetchall()
[('CREATE TABLE globs (progress INTEGER, CurrentPage INTEGER, LastPage INTEGER, AbortThread BOOLEAN, rowname TEXT)',)]
>>> c.execute("SELECT sql FROM sqlite_schema WHERE name='hubdata'").fetchall()
[('CREATE TABLE hubdata (siteVar TEXT, siteData TEXT)',)]
>>> c.execute("SELECT sql FROM sqlite_schema WHERE name='flash'").fetchall()
[('CREATE TABLE flash (message TEXT)',)]


globs: used to store global variables (I struggled to get globals working in python)

hubdata: used to store data extracted from HUB (again, because I could not get globals working)

flash: used to store flash messages (I could not get flash messages created in my threaded function
	to be recognized in my templates)

nxinx:
======

ubuntu@ip-172-31-21-6:/etc/nginx$ cat /etc/nginx/sites-available/my-server

server {
    listen 80;
    server_name ec2-3-86-52-33.compute-1.amazonaws.com;
    return 302 https://$server_name$request_uri;

    location /health {
            access_log on;
            return 200 "healthy\n";
    }
}

server  {
    listen 443 ssl;
    include snippets/self-signed.conf;
    include snippets/ssl-params.conf;
    #ssl_certificate /etc/ssl/certs/selfsigned.crt;
    #ssl_certificate_key /etc/ssl/private/selfsigned.key;

    #ssl_dhparam /etc/nginx/dhparam.pem;

    location / {
        include proxy_params;
        proxy_set_header   X-Forwarded-For $remote_addr;
        #proxy_set_header Host $http_host;
        proxy_pass "http://127.0.0.0:5000";
        #proxy_pass http://unix:/home/ubuntu/my-server/ipc.sock;
        proxy_headers_hash_max_size 512;
        proxy_headers_hash_bucket_size 128;
        proxy_http_version 1.1;
        proxy_set_header   "Connection" "";
    }
}

ubuntu@ip-172-31-83-158:~$ cat /etc/nginx/snippets/self-signed.conf
ssl_certificate /etc/ssl/certs/nginx-selfsigned.crt;
ssl_certificate_key /etc/ssl/private/nginx-selfsigned.key;

ubuntu@ip-172-31-83-158:~$ cat /etc/nginx/snippets/ssl-params.conf
# from https://cipherli.st/
# and https://raymii.org/s/tutorials/Strong_SSL_Security_On_nginx.html

ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
ssl_prefer_server_ciphers on;
ssl_ciphers "EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH";
ssl_ecdh_curve secp384r1;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;
ssl_stapling on;
ssl_stapling_verify on;
resolver 8.8.8.8 8.8.4.4 valid=300s;
resolver_timeout 5s;
# Disable preloading HSTS for now.  You can use the commented out header line that includes
# the "preload" directive if you understand the implications.
#add_header Strict-Transport-Security "max-age=63072000; includeSubdomains; preload";
add_header Strict-Transport-Security "max-age=63072000; includeSubdomains";
add_header X-Frame-Options DENY;
add_header X-Content-Type-Options nosniff;

ssl_dhparam /etc/ssl/certs/dhparam.pem;


ubuntu@ip-172-31-21-6:/etc/nginx$ ls -l /etc/nginx/sites-enabled
total 0
lrwxrwxrwx 1 root root 36 Sep  5 21:38 my-server -> /etc/nginx/sites-available/my-server

systemd:
===========

ubuntu@ip-172-31-21-6:/etc/nginx$ cat /etc/systemd/system/my-server.service
[Unit]
Description=Flask Web Application Server using Gunicorn
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/hub
Environment="PATH=/home/ubuntu/hub/venv/bin"
ExecStart=/bin/bash -c 'source /home/ubuntu/hub/venv/bin/activate; /home/ubuntu/hub/venv/bin/gunicorn -c /home/ubuntu/hub/gunicorn.conf.py wsgi:app'
#ExecStart=/bin/bash -c 'source /home/ubuntu/hub/venv/bin/activate; /home/ubuntu/hub/venv/bin/gunicorn -w 1 --bind 0.0.0.0:5000 --log-level=debug wsgi:app'
#ExecStart=/bin/bash -c 'source /home/ubuntu/hub/venv/bin/activate; /home/ubuntu/hub/venv/bin/gunicorn -w 1 --bind 0.0.0.0:5000 wsgi:app --error-logfile /var/log/gunicorn/error.log --access-logfile /var/log/gunicorn/access.log --capture-output --log-level debug'
#ExecStart=/bin/bash -c 'source /home/ubuntu/hub/venv/bin/activate; /home/ubuntu/hub/venv/bin/gunicorn -w 1 --bind unix:/home/ubuntu/my-server/ipc.sock wsgi:app'
Restart=always

[Install]
WantedBy=multi-user.target

ubuntu@ip-172-31-21-6:/etc/nginx$ cat /home/ubuntu/hub/gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 3
# Access log - records incoming HTTP requests
accesslog = "/home/ubuntu/hub/gunicorn.access.log"
# Error log - records Gunicorn server goings-on
errorlog = "/home/ubuntu/hub/gunicorn.error.log"
# Whether to send Django output to the error log
capture_output = True
# How verbose the Gunicorn error logs should be
loglevel = "debug"
timeout=10000
worker_class = "gevent"
pidfile="/home/ubuntu/hub/gunicorn.pid"

ubuntu@ip-172-31-21-6:/etc/nginx$ cat /home/ubuntu/hub/gunicorn.pid
18792

logrotate:
===========

ubuntu@ip-172-31-21-6:/etc/nginx$ cat /etc/logrotate.d/my-server
/home/ubuntu/hub/gunicorn.error.log
/home/ubuntu/hub/gunicorn.access.log
{
    compress
    missingok
    rotate 5
    notifempty
    size 5M
    dateext
    dateformat -%Y%-%m-%d
    postrotate
        kill -USER1 $(cat /home/ubuntu/hub/gunicorn.pid)
}

network ports:
==============

ubuntu@ip-172-31-83-158:~$ sudo netstat -nap|egrep ':5000|:80|:443'
tcp        0      0 0.0.0.0:5000            0.0.0.0:*               LISTEN      21494/python3
tcp        0      0 0.0.0.0:443             0.0.0.0:*               LISTEN      21624/nginx: master
tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN      21624/nginx: master
tcp        0      0 172.31.83.158:40370     54.165.17.230:80        TIME_WAIT   -

other linux:
=============

ubuntu@ip-172-31-83-158:~$ cat /etc/resolv.conf
# This is /run/systemd/resolve/stub-resolv.conf managed by man:systemd-resolved(8).
# Do not edit.
#
# This file might be symlinked as /etc/resolv.conf. If you're looking at
# /etc/resolv.conf and seeing this text, you have followed the symlink.
#
# This is a dynamic resolv.conf file for connecting local clients to the
# internal DNS stub resolver of systemd-resolved. This file lists all
# configured search domains.
#
# Run "resolvectl status" to see details about the uplink DNS servers
# currently in use.
#
# Third party programs should typically not access this file directly, but only
# through the symlink at /etc/resolv.conf. To manage man:resolv.conf(5) in a
# different way, replace this symlink by a static file or a different symlink.
#
# See man:systemd-resolved.service(8) for details about the supported modes of
# operation for /etc/resolv.conf.

nameserver 127.0.0.53
options edns0 trust-ad
search ec2.internal


ubuntu@ip-172-31-83-158:~$ cat /etc/hosts
127.0.0.1 localhost

# The following lines are desirable for IPv6 capable hosts
::1 ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
ff02::3 ip6-allhosts

ubuntu@ip-172-31-83-158:~$ hostname
ip-172-31-83-158

ssl:
====

ubuntu@ip-172-31-83-158:~$ ls -l /etc/ssl/certs/nginx-selfsigned.crt
-rw-r--r-- 1 root root 1489 Sep 16 11:31 /etc/ssl/certs/nginx-selfsigned.crt


ubuntu@ip-172-31-83-158:~$ cat /etc/ssl/certs/nginx-selfsigned.crt
-----BEGIN CERTIFICATE-----
MIIEHzCCAwegAwIBAgIUBara8SLPX3vRHe3MUIEcp5aZ8IEwDQYJKoZIhvcNAQEL
BQAwgZ4xCzAJBgNVBAYTAlVTMQswCQYDVQQIDAJPSDELMAkGA1UEBwwCQ0IxDTAL
BgNVBAoMBFVXQ08xDDAKBgNVBAsMA1RBWDEvMC0GA1UEAwwmZWMyLTMtODYtNTIt
MzMuY29tcHV0ZS0xLmFtYXpvbmF3cy5jb20xJzAlBgkqhkiG9w0BCQEWGHRpbW15
dGhldGF4bWFuQGdtYWlsLmNvbTAeFw0yMjA5MTYxMTMxMzRaFw0yMzA5MTYxMTMx
MzRaMIGeMQswCQYDVQQGEwJVUzELMAkGA1UECAwCT0gxCzAJBgNVBAcMAkNCMQ0w
CwYDVQQKDARVV0NPMQwwCgYDVQQLDANUQVgxLzAtBgNVBAMMJmVjMi0zLTg2LTUy
LTMzLmNvbXB1dGUtMS5hbWF6b25hd3MuY29tMScwJQYJKoZIhvcNAQkBFhh0aW1t
eXRoZXRheG1hbkBnbWFpbC5jb20wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQDhpsF55SFOHnNYvT3RkSfRqTwaga2OrvmAgh06tj/G6ReCYOiQPq2iQn5r
Ytaqztt3aDrfoZpegYECcxrS/bUpqCMuddcTEDOTHb+zm5UjqqOAMK0Cu1o+jJ4H
xXNCDST2KzhaUCb3bl0k1NUjEcEiFUU5dGiQnC2poWf95UZ7e9dh2IANnjd0vTTM
JtTfTxYa4gfPxGGVa7aXyjzJFA+96L/yQ7BI6oIXR0m+vRfGLrBqsgP+jcqAiG4l
ylbdJJE2JGlCWKjfQ3ZFm4zcBXPICx92NEsp46dFCx8xr1XzpZVq18llzkzZ43vK
QvsX5i7drwtXr2P2kLeNnplYLMlLAgMBAAGjUzBRMB0GA1UdDgQWBBSdZ1mf4Tcm
W9takhX0ZNkmiqRMGjAfBgNVHSMEGDAWgBSdZ1mf4TcmW9takhX0ZNkmiqRMGjAP
BgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQAWPu8BYKLjqI5aiPkn
shg/j3XNwcCUCS/3tkp+WxU4k9LA5mviqI0XVzb8WNi9d85ueFOXXm3CGyXkNayF
9W5RW0riVwisJS6fGL/IGwkA5tkjvObs/Chbj7eVoVJKgdkykEhWemB7fSh/XUB/
A8NMSiFhopa2PyI8QsfQpFPmMfZ2nZslsFnSSNbXfACK8LjNj/mABD7ugGxYHxWX
NOcVpNikpl5dzFwuiSke2H24lwE0DCDCiyFY0hDXQAsFFvpMNcbM3QhPDbSspui7
KIWVth32sEnLWFEZ2ICaGJBrJi9u0lRyMFfs4eGPrxSFrsMQ1J0DJHKktBgq4uUg
QMTT
-----END CERTIFICATE-----

ubuntu@ip-172-31-83-158:~$ keytool -printcert -file /etc/ssl/certs/nginx-selfsigned.crt
Owner: EMAILADDRESS=timmythetaxman@gmail.com, CN=ec2-3-86-52-33.compute-1.amazonaws.com, OU=TAX, O=UWCO, L=CB, ST=OH, C=US
Issuer: EMAILADDRESS=timmythetaxman@gmail.com, CN=ec2-3-86-52-33.compute-1.amazonaws.com, OU=TAX, O=UWCO, L=CB, ST=OH, C=US
Serial number: 5aadaf122cf5f7bd11dedcc50811ca79699f081
Valid from: Fri Sep 16 11:31:34 UTC 2022 until: Sat Sep 16 11:31:34 UTC 2023
Certificate fingerprints:
         SHA1: 0A:B0:CD:B2:72:04:D9:8D:BD:02:07:2A:83:2A:BC:B3:46:E2:6B:5E
         SHA256: 35:18:38:D7:48:B9:61:2C:C9:B3:F1:80:65:02:D9:17:D5:08:54:F3:B3:4D:2C:A6:47:45:3A:57:B2:AD:47:05
Signature algorithm name: SHA256withRSA
Subject Public Key Algorithm: 2048-bit RSA key
Version: 3

Extensions:

#1: ObjectId: 2.5.29.35 Criticality=false
AuthorityKeyIdentifier [
KeyIdentifier [
0000: 9D 67 59 9F E1 37 26 5B   DB 5A 92 15 F4 64 D9 26  .gY..7&[.Z...d.&
0010: 8A A4 4C 1A                                        ..L.
]
]

#2: ObjectId: 2.5.29.19 Criticality=true
BasicConstraints:[
  CA:true
  PathLen: no limit
]

#3: ObjectId: 2.5.29.14 Criticality=false
SubjectKeyIdentifier [
KeyIdentifier [
0000: 9D 67 59 9F E1 37 26 5B   DB 5A 92 15 F4 64 D9 26  .gY..7&[.Z...d.&
0010: 8A A4 4C 1A                                        ..L.
]
]

ubuntu@ip-172-31-83-158:~$ sudo ls -l /etc/ssl/private/
total 4
-rw------- 1 root root 1708 Sep 16 11:30 nginx-selfsigned.key

