import sqlite3
from sqlite3 import Error
import gevent
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session, Response, jsonify
import json
import os.path
from werkzeug.utils import secure_filename
import requests
from bs4 import BeautifulSoup
import re
import gyr
import ast
import copy
from collections import OrderedDict
import time
#from tqdm import tqdm, trange
from threading import Thread

app = Flask(__name__)
app.secret_key = 'abc123andmoresecretsauce'
SitesDict = {} # This should make it a global, accessible inside functions.  For some reason not working.
#global progress, CurrentPage, LastPage, AbortThread
#progress = 0
#CurrentPage = 1
#LastPage = 1
#AbortThread = False
#print(__name__)

if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

@app.route('/')
def home():
    #app.logger.debug('home: progress = %d',progress)
    update_progress(0)
    flash_message=tims_get_flash_messages()
    if (flash_message):
      flash(flash_message)
    return render_template('home.html', codes=session.keys())

def tims_get_flash_messages():
    # This function will pull message from the flash database
    c=sqlite3.connect("hub.db")
    flash_message_cursor = c.execute("SELECT * from flash").fetchone()
    if flash_message_cursor:
      # not empty
      flash_message = flash_message_cursor[0]
      c.execute("DELETE from flash") # Empty out the table
      c.commit()
    else:
      flash_message = None
    c.close()
    return flash_message

def tims_put_flash_messages(msg):
    c=sqlite3.connect("hub.db")
    c.execute("INSERT INTO flash VALUES (?)", (msg,))
    # Should really do some error checking here
    c.commit()
    c.close()
    return

@app.route('/hub_authenticate')
def hub_authenticate():
    app.logger.debug('hub_authenticate')
    flash_message=tims_get_flash_messages()
    if (flash_message):
      flash(flash_message)
    update_progress(0) # Set progress back to zero
    return render_template('hub_authenticate.html')


@app.route('/hub_stats', methods=['GET','POST'])
def hub_stats():
    # If we reach this function, it means the User clicked the button to authenticate and gather data.  So do the following:
    # 1) Spawn a thread which will gather the data from the HUB
    # 2) Go to the hub_stats.html page.  This page will monitor progress and display progress bar.
    # 3) Once progress reaches 100, hub_stats.html will request HUB data, and go to display_hub_stats.html 
    # 4) display_hub_stats.html will display the HUB data

    app.logger.debug('hub_stats')
    email=request.form['hub_email']
    password=request.form['hub_password']
    
    app.logger.debug('hub_stats: starting thread for get_stats')
    t1 = Thread(target=get_stats, args=(email,password)) # Create the thread to generate progress, and gather stats
    t1.start() # Start the thread

    app.logger.debug('hub_stats: rendering hub_stats')
    return render_template('hub_stats.html')

@app.route('/display_hub_stats', methods=['GET','POST'])
def display_hub_stats():

    app.logger.debug('display_hub_stats')
    SitesDict = read_siteData() # Get the data from sql DB
    app.logger.debug('display_hub_stats: type(SitesDict) = %s', type(SitesDict))
    app.logger.debug('display_hub_stats: SitesDict = %s', json.dumps(SitesDict))
    return render_template('display_hub_stats.html', sites=SitesDict, header=list(SitesDict.values())[0])

@app.route('/download_csv', methods=['GET','POST'])
def download_csv():
    app.logger.debug('download_csv')
    #site_data_in_download = request.args.get('sites')
    #app.logger.debug('download_csv: site_data_in_download = %s', site_data_in_download)
    #app.logger.debug('download_csv: type(site_data_in_download) = %s', type(site_data_in_download))
    ##sess_data_in_csv = session.get('HubSites', None)
    ##print(f'In download_csv: site_data_in_download = {site_data_in_download}')
    ##print(f'in download_csv: type for site_data_in_download: {type(site_data_in_download)}')
    #my_dict = ast.literal_eval(site_data_in_download) # needed because it gets typed as a string
                                                      # coming from the template (!?)
    ##print(f'in download_csv: type for my_dict: {type(my_dict)}')
    HubSitesCsv = dict_to_csv(read_siteData())
    #print(f'In download_csv: HubSitesCSV = {HubSitesCsv}')
    return Response(HubSitesCsv, mimetype="text/csv", headers={"Content-disposition": "attachment; filename=myplot.csv"})

def update_sitedata(SiteData):
    c=sqlite3.connect("hub.db")
    ptuple=(json.dumps(SiteData),) # convert dictionary data to a string
    c.execute("UPDATE hubdata SET siteData=? WHERE siteVar='var1'", (ptuple))
    c.commit()
    c.close()
    return

def read_siteData():
    c=sqlite3.connect("hub.db")
    SiteData = json.loads(c.execute("SELECT siteData from hubdata WHERE siteVar='var1'").fetchone()[0])
    c.close()
    return SiteData

def update_progress(progress):
    c=sqlite3.connect("hub.db")
    ptuple=(progress,)
    c.execute("UPDATE globs SET progress=? WHERE rowname='Globals'", (ptuple))
    c.commit()
    c.close()
    return

def read_progress():
    c=sqlite3.connect("hub.db")
    progress = c.execute("SELECT progress from globs").fetchone()[0]
    c.close()
    return progress

@app.route('/get_progress')
def get_progress():
    progress = read_progress()
    app.logger.debug('get_progress: progress=%d', progress)
    return jsonify(result=progress)

def get_stats(email,  password):
    app.logger.debug('get_stats')
    LOGIN_FAILED = -1
    CurrentPage = 0
    global SitesDict # Since this function is going to update this global value
    #global progress
    #global  CurrentPage
    #global LastPage
    #global AbortThread
    #print(f'in get_stats(): email={email}, password={password}, urls={gyr.urls}')
    
    # authentication_data is a dictionary that is sent with GET/POST requests to authenticate.
    # Need to first set the email and password within authentication_data
    gyr.authentication_data['user[email]'] = email 
    gyr.authentication_data['user[password]'] = password
    
    with requests.session() as s:
        app.logger.debug('get_stats:with requests.session')
        # Initial authentication and obtaining session ID
        r = s.post(gyr.loginurl, data=gyr.authentication_data)
        a=BeautifulSoup(r.content, 'html.parser')
        loginIndication = a.find('div', {'class':'grid__item'}).text.strip()
        if loginIndication != 'Signed in successfully.' and loginIndication != 'You are already signed in.':
            app.logger.debug('get_stats:with requests.session:loginIndication')
            app.logger.debug('get_stats:with requests.session: r.content = %s', r.content)
            alertString = "Login failure: return code = " + str(r.status_code)
            app.logger.debug('get_stats:with requests.session: LOGIN_FAILED = %d', LOGIN_FAILED)
            progress = LOGIN_FAILED
            update_progress(progress) # This will cause JavaScript on client to see failed login
            tims_put_flash_messages('Login failed.  Please try again.')
            return 

        StatesDict = get_hub_states(r) # Get initialized dictionary of all possible return status
        SitesDict = get_hub_sites(r, StatesDict) # Get initialized dictionary for all sites 
        
        # Pull up page with all clients data
        r3 = s.post(gyr.all_clients_url)
        #r3 = s.post(gyr.all_clients_url, data=gyr.authentication_data)
        #print(f'get_stats: Status code for all-clients POST is {r3.status_code}')
        a=BeautifulSoup(r3.content, 'html.parser')
        
        CurrentPage=int(a.find('nav', {'role': 'navigation'}).find_all('em', {'aria-current': 'page'})[0].text)
        LastPage=int(a.find('nav', {'role': 'navigation'}).find_all('a', {'aria-label': re.compile('Page.*')})[-1].string)
        #print(f'get_stats: Page {CurrentPage} of {LastPage}')
      
        # Start thread of function that will update progress
        #t1 = Thread(target=fn_to_thread) # Create the thread
        #t1.start() # Start the thread
    
        NoNext = False
        #NoNext = True
        #LastPage=3
        while not NoNext:
            app.logger.debug('get_stats:with requests.session:while not NoNext:CurrentPage=%d', CurrentPage)
            b=a.find_all('tr')
            for i in b[1:]: # Each rows after the header row
                #if i.th['class'][0] != "index-table__header":
                j=i.find_all('td') # List of all cells in this row
                site=j[2].text.strip() # Sitename for this row of cells
                try:
                    status=i.find('div', {'class':'tax-return-list__status label label--status'})['data-status'] # Status for this site
                    SitesDict[site][status] += 1
                except: # In case there is no return status, which we have seen
                    pass
            try:
                NextPageLink=a.find('nav', {'role': 'navigation'}).find_all('a', {'class': 'next_page'})[0]['href']
            except:
                NoNext = True
            if not NoNext:
                url='https://www.getyourrefund.org' + NextPageLink
                app.logger.debug('get_stats:with requests.session:while not NoNext:url=%s', url)
                r3 = s.post(url,timeout=20)
                app.logger.debug('get_stats: return code from HUB = %s', str(r.status_code))
                #r3 = s.post(url, data=gyr.authentication_data)
                a=BeautifulSoup(r3.content, 'html.parser') 
                #app.logger.debug('r3.content = %s', r3.content)
            progress = int(100 * (CurrentPage/LastPage))
            update_progress(progress)
            app.logger.debug('get_stats:with requests.session:progress=%d', progress)
            # if CurrentPage == LastPage:
            #     NoNext = True
            CurrentPage += 1
            #print(f'Current Page = {CurrentPage}, next link = {url}')
            debug_mode=False
            if debug_mode:
              if CurrentPage > 5: #Code for debugging
                   NoNext = True
    
    CurrentPage = 0
    #AbortThread = True
    progress = 100
    update_progress(progress)
    update_sitedata(SitesDict)
    app.logger.debug('get_stats: about to return')
    app.logger.debug('get_stats: SitesDict = %s', json.dumps(SitesDict))
    
    return SitesDict, "Success"

def get_hub_sites(r, StatesDict):
    soup=BeautifulSoup(r.content, 'html.parser')
    s=soup.body.script.contents[0].strip() #This returns a string which includes a dictionary
    # Need to strip garbage from the string, then convert to a dictionary
    t=ast.literal_eval(re.sub(r';$','',re.sub(r'^.* = ','',s)))
    SitesDict = {}
    for d in t:
        SiteName = d['name']
        if 'Closed' not in SiteName:
            SitesDict[SiteName] = copy.deepcopy(StatesDict) # Must make a copy.deepcopy of the states dict
    return SitesDict # Return a dictionary of sites, each site is a dict with an initialized set of states
    # SitesList = []
    # for d in t:
    #     SiteName = d['name']
    #     if 'Closed' not in SiteName:
    #         SitesList.append(SiteName) = StatesList # 
    # return SitesList # Return a List of tuples.  site is a dict with an initialized set of states


def get_hub_states(r):
    soup=BeautifulSoup(r.content, 'html.parser')
    #l=[]
    StatesDict = {}
    for i in soup.find("select", {"class": "select__element"}).findAll("option"):
        ReturnState = i.get("value")
        if '_' in ReturnState:
            StatesDict[ReturnState] = 0
    return StatesDict # Return a dictionary of states, initialized to zero


def dict_to_csv(dict):
    #print(f'In dict_to_csv: dict = {dict}')
    #time.sleep(2)
    #print(type(dict))
    #print(f'Before header: {list(dict)}')
    #print(f'Before header: {dict}')
    header = 'Site,' + ','.join(list(dict[list(dict)[0]].keys())) + '\n'
    body = ''
    for k in dict.keys():
        l1 = list(dict[k].values())
        l1c = [ str(x) for x in l1 ]
        value_row = k + ',' + ','.join(l1c) + '\n'
        body += value_row
    return (header + body)

@app.route('/your-url', methods=['GET','POST'])
def your_url():
    if request.method == 'POST':
        urls = {}

        if os.path.exists('urls.json'):
            with open('urls.json') as urls_file:
                urls = json.load(urls_file)

        if request.form['code'] in urls.keys():
            flash('That short name has already been taken.  Select another name')
            return redirect(url_for('home'))

        if 'url' in request.form.keys():
            urls[request.form['code']] = {'url': request.form['url'] }
        else:
            f = request.files['file']
            full_name = request.form['code'] + secure_filename(f.filename)
            f.save('/home/tucker/edu/url-shortener2/static/user_files/' + full_name)
            urls[request.form['code']] = {'file': full_name }

        with open('urls.json', 'w') as url_file:
            json.dump(urls, url_file)
            session[request.form['code']] = True
        return render_template('your_url.html', code=request.form['code'])
    else:
        return redirect(url_for('home'))

@app.route('/<string:code>')
def redirect_to_url(code):
    if os.path.exists('urls.json'):
        with open('urls.json') as urls_file:
            urls = json.load(urls_file)
            if code in urls.keys():
                if 'url' in urls[code].keys():
                    return redirect(urls[code]['url'])
                else:
                    return redirect(url_for('static', filename='user_files/' + urls[code]['file']))
    return abort(404)

@app.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404

if __name__ == "__main__":
    #global progress, CurrentPage, LastPage
    #progress = 0
    app.run()

# Make sure to run the following in your shell if you are using this main code
# export FLASK_APP=app.py (or whatever this filename is)
# export FLASK_ENV=development
#   or for windows:
# set FLASK_APP=app.py
# set FLASK_ENV=development
# $env:FLASK_APP="app.py"
# $env:FLASK_ENV="development"
#
# start virtual environment: source venv/bin/activate
# 
# git
# git config --global user.email "tim@ttimtucker.com"
# git config --global user.name "Tim Tucker"
# git add <filename>
# git commit -m "first commit" 
# git commit -a
# git branch -M main
# ??? git remote add origin https://github.com/ttimtucker/hub-scraper.git ???
# 
# git token from web page: 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
# git push https://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@github.com/ttimtucker/hub-scraper.git/

