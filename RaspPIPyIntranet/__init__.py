import sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, \
 abort, render_template, flash
from wtforms import Form, BooleanField, TextField, DateTimeField, IntegerField, SubmitField, HiddenField,validators, TextAreaField, RadioField, PasswordField
from apscheduler.scheduler import Scheduler
from flask_mail import Mail, Message
import RPi.GPIO as GPIO # Allows us to call our GPIO pins and names it just GPIO
import subprocess
import datetime
import os
import time
import sys
import random
import logging


# create our little application :)
app = Flask(__name__)


    #configuration
    # Load default config and override config from an environment variable
app.config.update(dict(
        DATABASE = 'RaspPIPyIntranet/RaspPIpyIntranet.db',
        DEBUG = False,
        SECRET_KEY = 'development key',
        USERNAME = 'admin',
        PASSWORD = 'default'
))
app.config.from_envvar('RASPYINTRANET_SETTINGS', silent=True)

global cfgSetup



def getActivity():
    try:
        dbconn = sqlite3.connect(app.config['DATABASE'])
        scur=dbconn.cursor()
    #    scur.execute('SELECT datelogged, isdetection FROM aa_detections ')
        scur.execute('SELECT * FROM (SELECT datelogged, ?, timelogged FROM aa_detections WHERE isdetection = 1 UNION SELECT datelogged, ?, timelogged FROM aa_detections WHERE isdetection = 0 UNION SELECT datetime datelogged, comment, 0 FROM ac_imgcomments) ORDER BY datelogged, timelogged DESC LIMIT 50', ['Sensor Alert', 'Random Photo'])
        recsetup = scur.fetchall()
        scur.close()
        dbconn.close()
        return recsetup
    except sqlite3.Error, e:
        return []
        

class SetupForm(Form):
    recid = HiddenField("")
    sitename =  TextField('Site name',[validators.Length(min=3, max=50)])
    typeofcamera = RadioField('Type Of Camera', choices = [('usb','USB Web Cam'),('raspcam','Raspberry PI Cam'),('custom','Custom')])
    cameracmd =  TextField('System Command Web Cam', [validators.Length(min=0, max=300)])
    alarm_mode = BooleanField('Email Alarm Mode', default = False)
    random_mode = BooleanField('Random Photo Mode', default = False)
    photo_freq = TextField('Daily Photo Freq', default = '0')
    from_time = TextField('Start Time to take Shots hh:mm',[validators.Length(min=5, max = 5)])
    to_time = TextField('End Time hh:mm',[validators.Length(min=5, max = 5)])
    mailer_server = TextField('Mail Server')
    mail_port = TextField('Mail Port')
    mail_use_ssl = TextField('Mail Use SSL')
    mail_username = TextField('Mail Username')
    mail_password = PasswordField('Mail Password')

class ImageForm(Form):
    recImgName = HiddenField("")
    recFolder = HiddenField("")
    txtcomment = TextField("Comment and Email Text", [validators.Length(min=5, max=300)])
    dtPhoto = HiddenField("", default='na')

class SetupConfig:
  def __init__(self, palrm_mode, p_rndm_mode, p_site_name, p_photo_freq, p_cam_mode, p_custom, pstarthr,pstartmin, pendhr, pendmin, p_mailer_server, p_mail_port, p_mail_use_ssl, p_mail_username, p_mail_password):
    self.alarm_mode = True if palrm_mode == 1 else False
    self.random_mode = True if p_rndm_mode == 1 else False
    self.site_name  = p_site_name  
    self.photo_freq = p_photo_freq  
    self.lsttime = []
    self.icnt = 0
    self.cam_mode = p_cam_mode
    self.customcmd = p_custom
    self.starthr = pstarthr
    self.startmin = pstartmin
    self.endhr = pendhr
    self.endmin = pendmin
    self.mailer_server = p_mailer_server
    self.mailer_port = p_mail_port
    self.mailer_use_ssl = p_mail_use_ssl
    self.mailer_username = p_mail_username
    self.mailer_password = p_mail_password
    
    


def sendemail(filenm, emailtext):
    global cfgSetup
    msg = Message(
              'RaspPIPYIntranet Message',
           sender=cfgSetup.mailer_username,
           recipients=
               [cfgSetup.mailer_username])
    msg.body = emailtext
    with app.open_resource(filenm) as fp:
        msg.attach(fp, "image/jpg", fp.read())
    with app.app_context():    
        mail.send(msg)
    return "Sent"



def boolcnv(pval):
    if pval == True:
        return 1
    else:
        return 0        

def get_setup():
    db = get_db()
    cur=db.cursor()
    cur.execute('select id, sitename, cameracmd, alarm_mode, random_mode, photo_freq, typeofcamera, starttime, endtime, mailer_server, mailer_port, mailer_use_ssl, mailer_username, mailer_password   from ab_setup')
    recsetup = cur.fetchone()
    return recsetup


     

def connect_db():
    return sqlite3.connect(app.config['DATABASE']) 

def init_db():
    """Creates the database tables."""
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
    

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

def get_setup():
    db = get_db()
    cur=db.cursor()

    cur.execute('select id, sitename, cameracmd, alarm_mode, random_mode, photo_freq, typeofcamera, starttime, endtime, mailer_server, mailer_port, mailer_use_ssl, mailer_username, mailer_password from ab_setup')
    recsetup = cur.fetchone()
    return recsetup

def get_nearestdate(pdate):
    db = get_db()
    cur=db.cursor()
    cur.execute('select max(datelogged) from aa_detections where datelogged <= ? ',[pdate])
    detections = cur.fetchone()
    return detections[0]

def calculatesnaps() :
    # random passed on hourly frequency. Polls every minute
    global cfgSetup

    sstarttime = int('%s%s' % (cfgSetup.starthr, cfgSetup.startmin))
    sendtime = int('%s%s' % (cfgSetup.endhr, cfgSetup.endmin))
    
    icnt = 0
    while icnt < cfgSetup.photo_freq:
        smin = random.randint(1,60)
        shr = random.randint(1,24)
        sval = int('%d%02d' % (shr,smin))
	if (sval >= sstarttime and sval < sendtime) or (sstarttime == 0 and sendtime == 0):
            if sval not in cfgSetup.lsttime: 
                cfgSetup.lsttime.append(sval)
                icnt = icnt + 1
    cfgSetup.lsttime.sort() 
        

def get_detections(pndate):
    try:
        spath = "RaspPIPyIntranet/static/images/SnapView/%s" % pndate  
        sbasefolder = "images/SnapView/%s" % pndate 
        onlyfiles = os.listdir(spath)
        return onlyfiles
    except OSError,e:
        print 'No such file 1 %s' % e    
        return []

def insert_db(bAlarm):
    with app.app_context():
        db = get_db()
        vdate = time.strftime("%Y%m%d")
        vtime = datetime.datetime.today().strftime("%H%M")
        cur=db.cursor()
        cur.execute('select count(*) from aa_detections where datelogged = ?',[time.strftime("%Y%m%d")])
        row = cur.fetchone()
        if row[0] == 0 or bAlarm:
            db.execute('insert into aa_detections (datelogged, isdetection,timelogged) values (?, ?, ?)', [vdate,boolcnv(bAlarm),  int(datetime.datetime.today().strftime("%H%M"))])
            db.commit();

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


def getTop():
    try:
        db = get_db()
        cur=db.cursor()
        cur.execute('SELECT ? || ? || SUBSTR(imagename,-16,6) || ? || imagename,comment,datetime FROM ac_imgcomments ORDER BY datetime DESC LIMIT 3',['images/SnapView/',datetime.datetime.today().strftime("%C"),'/'])
        recresult = cur.fetchall()
        cur.close()
        return recresult
    except sqlite3.Error, e:
        return []

def takecamera(bAlarm): 
    try:    
        global time_stamp
        global cfgSetup 
   
        time_now = datetime.datetime.today()
        if ((time_stamp + datetime.timedelta(minutes=1)) < time_now): 
            d = datetime.datetime.today().strftime("%y%m%d%H%M%S")
            df = datetime.datetime.today().strftime("%Y%m%d")
            sfolder = 'RaspPIPyIntranet/static/images/SnapView/%s' % df
            sfilename = 'image%s.jpg' % d
            if not os.path.isdir(sfolder):
                os.makedirs(sfolder)
            if cfgSetup.cam_mode == 'usb':
                output = subprocess.Popen(['fswebcam', '-d', '/dev/video0', '-r', '640x480', '%s/%s' % (sfolder,sfilename)], stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE)
            elif  cfgSetup.cam_mode == 'raspcam':
                output = subprocess.Popen(['raspistill', '-o', '%s/%s' % (sfolder,sfilename)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                output = subprocess.Popen([cfgSetup.customcmd, '%s/%s' % (sfolder,sfilename)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = output.communicate()
            time_stamp = time_now
            insert_db(bAlarm)
            sfolder = 'static/images/SnapView/%s' % df
            sfolderfile = '%s/%s' % (sfolder,sfilename)
            if cfgSetup.alarm_mode and bAlarm == True:
                sendemail(sfolderfile, "Detection Triggered")
    except IOError, e:
        print 'No such file 2 %s' % e

# Create a function to run when the input is high
def inputRising(channel):
    takecamera(True)




def autoshot():
    global cfgSetup

    sStartTime =  cfgSetup.starthr +  cfgSetup.startmin 
    sEndTime = cfgSetup.endhr + cfgSetup.endmin 
    
    
    stime = datetime.datetime.today().strftime("%H%M")

    if cfgSetup.random_mode == 1 and ((sStartTime != "00:00" and sEndTime != "00:00") or (int(stime) > int(sStartTime) and int(stime) < int(sEndTime)  )):
        if int(stime) == cfgSetup.lsttime[0]:
            takecamera(False)
            if len(cfgSetup.lsttime) > 1:
                del cfgSetup.lsttime[0]
            else:
                del cfgSetup.lsttime[0]
                calculatesnaps()
               

def setup_app(configfile=None):
    global time_stamp
    global pageno
    global nopage
    global cfgSetup 
    logging.basicConfig()
    pageno = 1
    nopage = 4
    time_stamp = datetime.datetime.today()
    GPIO.setmode(GPIO.BCM)  # Set's GPIO pins to BCM GPIO numbering
    #INPUT_PIN = 17           # Sets our input pin, in this example I'm connecting our button to pin 4. Pin 0 is the SDA pin so I avoid using it for sensors/buttons   
    GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Set our input pin to be an input
    GPIO.add_event_detect(17, GPIO.RISING, inputRising)
    init_db()
    # get setup     
    with app.app_context():
        db = get_db()
        cur=db.cursor()
        cur.execute('select alarm_mode, random_mode, sitename, photo_freq, typeofcamera, cameracmd, starttime, endtime, mailer_server,mailer_port,mailer_use_ssl,mailer_username,mailer_password  from ab_setup where id = 1')
        recsetup = cur.fetchone()
        sstart=""
        send=""
        sstart = recsetup[6]
        send = recsetup[7]
	cfgSetup = SetupConfig(recsetup[0],recsetup[1], recsetup[2], recsetup[3], recsetup[4], recsetup[5], sstart[0:2],sstart[3:5], send[0:2], send[3:5], recsetup[8], recsetup[9],recsetup[10],recsetup[11],recsetup[12])
        if cfgSetup.random_mode == 1:
                calculatesnaps()
		
        bval = False
        if cfgSetup.mailer_use_ssl == "True":
            bval = True
        app.config.update(dict(
            MAIL_SERVER= cfgSetup.mailer_server,
            MAIL_PORT=int(cfgSetup.mailer_port),
            MAIL_USE_SSL=bval,
            MAIL_USERNAME = cfgSetup.mailer_username,
            MAIL_PASSWORD = cfgSetup.mailer_password
        ))
       
    return app;

@app.route('/about', methods=['GET','POST'])
def about():
        return render_template('about.html')

@app.route('/setup', methods=['GET','POST'])
def setup():
   if request.method == 'GET':
         recsetup = get_setup()
         form = SetupForm(request.form, recid = recsetup[0], sitename = recsetup[1], cameracmd  = recsetup[2],  alarm_mode = recsetup[3], random_mode = recsetup[4], photo_freq = recsetup[5], typeofcamera = recsetup[6], from_time = recsetup[7], to_time =  recsetup[8], mailer_server = recsetup[9], mail_port = recsetup[10], mail_use_ssl = recsetup[11], mail_username = recsetup[12], mail_password = recsetup[13])
         form.alarm_mode.data = recsetup[3];
         return render_template('setup.html', form=form)   
   elif request.method == 'POST':
        form = SetupForm(request.values)     
        if not form.validate():
            flash('Invalid')
            return render_template('setup.html', form=form)
        else:
            # Code to update database added here
             with app.app_context():
                db = get_db()
                sstart = form.from_time.data
                send = form.to_time.data
                db.execute('UPDATE ab_setup SET sitename = ?, cameracmd = ?, alarm_mode = ?, random_mode = ?, photo_freq = ?, typeofcamera = ?, starttime = ?, endtime = ?, mailer_server = ?, mailer_port = ?, mailer_use_ssl = ?, mailer_username = ?, mailer_password = ? where id = ? ',[form.sitename.data, form.cameracmd.data , boolcnv(form.alarm_mode.data), boolcnv(form.random_mode.data),  form.photo_freq.data, form.typeofcamera.data, sstart, send, form.mailer_server.data, form.mail_port.data, form.mail_use_ssl.data, form.mail_username.data, form.mail_password.data,form.recid.data])
                db.commit()
                flash('Configuration Updated')
                recsetup = get_setup()
                form = SetupForm(request.form, recid = recsetup[0], sitename = recsetup[1], cameracmd  = recsetup[2],  alarm_mode = recsetup[3], random_mode = recsetup[4], photo_freq = recsetup[5], typeofcamera = recsetup[6], from_time = recsetup[7], to_time =  recsetup[8], mailer_server = recsetup[9], mail_port = recsetup[10], mail_use_ssl = recsetup[11], mail_username = recsetup[12], mail_password = recsetup[13])
                return render_template('setup.html', form=form )

@app.route('/process', methods=["POST"])
def process():
    pdate = request.form['dtPhoto']
    if request.form['dtPhoto'] == 'na':
        saction = request.form['cmdbtn']
        sdate = request.form['recFolder']
        sfile = request.form['recImgName']
        if saction == 'Email':
            sfolderfile = 'static/images/SnapView/%s/%s' % (sdate,sfile)
            scomment = request.form['txtcomment']
            sendemail(sfolderfile, scomment)
        elif saction == 'Delete':
            spathfile = "static/images/SnapView/%s/%s" % (sdate,sfile)
            os.remove(spathfile)
        elif saction == 'Save':
            # savecomment
            with app.app_context():
                db = get_db()
                scomment = request.form['txtcomment']
                db.execute('insert into ac_imgcomments (imagename, datetime, comment) values (?,?,?)', [sfile,sdate,scomment])
                db.commit();
        elif saction == 'Return':
            sdate = request.form['recFolder']
    else:
        sdate = datetime.datetime.strptime(pdate, "%Y-%m-%d").strftime('%Y%m%d')
    ndate = get_nearestdate(sdate)
    if ndate <> None:
        #logic to list directory contents will go here
        onlyfiles = get_detections(ndate)
        sbasefolder = "images/SnapView/%s" % ndate
        nfdate = datetime.datetime.strptime(str(ndate), "%Y%m%d").strftime('%Y-%m-%d')
        sact = getActivity()
        sres = getTop()
    else:
        onlyfiles = []
        sbasefolder = ""
        nfdate = None
        sact = []
        sres = [] 
    return render_template('index.html', detections=ndate, files=onlyfiles, path=sbasefolder, dtvalue=nfdate, activities=sact, recent = sres)        
 
@app.route('/showimg/<pname>/<pfile>')
def showimg(pname, pfile):
    db = get_db()
    cur = db.cursor()
    cur.execute('select comment from ac_imgcomments where imagename = ?', [pfile])
    scomments = cur.fetchone()
    if scomments == None:
        scomment = ''
    else:
        scomment = scomments[0]
    form = ImageForm(request.form, recImgName=pfile, recFolder=pname, txtcomment=scomment)
    return render_template('showimg.html', form=form, pimg = pfile, pfolder = 'images/SnapView/%s' % pname )  

@app.route('/')
def show_entries():
        db = get_db()
        cur=db.cursor()
        cur.execute('select max(datelogged) from aa_detections order by id desc')
        detections = cur.fetchone()
        cur.close()
        sdate = detections[0]
        if sdate == None:
            sdate = datetime.datetime.today().strftime("%y%m%d%H%M%S")
            onlyfiles = []
            spath = "static/images/SnapView"  
            sbasefolder = "images/SnapView/"
            nfdate = datetime.datetime.today().strftime("%Y-%m-%d")
        else:
            
            spath = "static/images/SnapView/%s" % sdate  
            sbasefolder = "images/SnapView/%s" % sdate 
            nfdate = datetime.datetime.strptime(str(sdate), "%Y%m%d").strftime('%Y-%m-%d') 
            onlyfiles = get_detections(sdate)
        sact = getActivity()
        sres = getTop()
        return render_template('index.html', detections=sdate, files=onlyfiles, path=sbasefolder, dtvalue=nfdate, activities = sact, recent = sres)        



# fswebcam -d /dev/video0 -r 640x480 /opt/SnapView/test1.jpg
with app.app_context():
    setup_app()
    mail=Mail(app)
    global sched
    sched = Scheduler()
    sched.add_interval_job(autoshot, seconds = 60)
    sched.start()
    
