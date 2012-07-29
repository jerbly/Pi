'''
Created on 21 Jul 2012

@author: Jeremy Blythe

screen - Manages the Textstar 16x2 4 button display

Read the blog entry at http://jeremyblythe.blogspot.com for more information
'''
import serial
import datetime
import time
import subprocess
import twitter
import urllib2
import json

CLEAR = chr(12)
ESC = chr(254)
BLOCK = chr(154)

POLL_TICKS = 15
REFRESH_TICKS = 300

class Display():
    """ Manages the 16x2 4 button display:
        on_tick called every 0.1 seconds as part of the main loop after the button read
        on_poll called every 1.5 seconds
        on_page called when a new page has been selected
        on_refresh called every 30 seconds"""
    def __init__(self,on_page=None,on_poll=None,on_tick=None,on_refresh=None):
        # Start the serial port
        self.ser = serial.Serial('/dev/ttyAMA0',9600,timeout=0.1)
        # Callbacks
        self.on_page = on_page
        self.on_poll = on_poll
        self.on_tick = on_tick
        self.on_refresh = on_refresh

        self.page = 'a'
        self.poll = POLL_TICKS
        self.refresh = REFRESH_TICKS

    def position_cursor(self,line,column):
        self.ser.write(ESC+'P'+chr(line)+chr(column))
    
    def scroll_down(self):
        self.ser.write(ESC+'O'+chr(0))
    
    def window_home(self):
        self.ser.write(ESC+'G'+chr(1))

    def clear(self):
        self.ser.write(CLEAR)

    def run(self):
        #show initial page
        display.ser.write('  Starting....  ')
        if self.on_page != None:
            self.on_page()
        #main loop
        while True:
            key = str(self.ser.read(1))
            if key != '' and key in 'abcd':
                self.page = key
                self.refresh = REFRESH_TICKS
                self.poll = POLL_TICKS
                if self.on_page != None:
                    self.on_page()
            else:
                self.refresh-=1
                if self.refresh == 0:
                    self.refresh = REFRESH_TICKS
                    if self.on_refresh != None:
                        self.on_refresh()
                        
                self.poll-=1
                if self.poll == 0:
                    self.poll = POLL_TICKS
                    if self.on_poll != None:
                        self.on_poll()
                        
                if self.on_tick != None:
                    self.on_tick()


display = None
# Start twitter
twitter_api = twitter.Api()

def write_datetime():
    display.position_cursor(1, 1)
    dt=str(datetime.datetime.now())
    display.ser.write('   '+dt[:10]+'   '+'    '+dt[11:19]+'    ')

def get_addr(interface):
    try:
        s = subprocess.check_output(["ip","addr","show",interface])
        return s.split('\n')[2].strip().split(' ')[1].split('/')[0]
    except:
        return '?.?.?.?'

def write_ip_addresses():
    display.position_cursor(1, 1)
    display.ser.write('e'+get_addr('eth0').rjust(15)+'w'+get_addr('wlan0').rjust(15))

def write_twitter():
    display.position_cursor(1, 1)
    try:
        statuses = twitter_api.GetUserTimeline('Raspberry_Pi')
        twitter_out = BLOCK
        for s in statuses:
            twitter_out+=s.text.encode('ascii','ignore')+BLOCK
        display.ser.write(twitter_out[:256])
    except:
        display.ser.write('twitter failed'.ljust(256))

def write_recent_numbers():
    display.position_cursor(1, 1)
    try:
        result = urllib2.urlopen("http://jerbly.uk.to/get_recent_visitors").read()
        j = json.loads(result)
        if len(j) > 0:
            entry = str(j[0]['numbers'][-1:])+' '+j[0]['countryName']
            display.ser.write(entry.ljust(32))
        else:
            display.ser.write('No entries found'.ljust(32))
    except:
        display.ser.write('jerbly.uk.to    failed'.ljust(32))

# Callbacks
def on_page():
    display.clear()
    display.window_home()
    if display.page == 'a':
        write_datetime()
    elif display.page == 'b':
        write_recent_numbers()
    elif display.page == 'c':
        write_twitter()
    elif display.page == 'd':
        write_ip_addresses()
        
def on_poll():
    if display.page == 'c':
        display.scroll_down()

def on_tick():
    if display.page == 'a':
        write_datetime()

def on_refresh():
    if display.page == 'b':
        write_recent_numbers()
    elif display.page == 'c':
        write_twitter()
    elif display.page == 'd':
        write_ip_addresses()

display = Display(on_page, on_poll, on_tick, on_refresh)            
display.run()

