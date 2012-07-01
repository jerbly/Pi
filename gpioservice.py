#!/usr/bin/python2
'''
Created on 18 Jun 2012

@author: Jeremy Blythe

GPIO service - provides simple management of Raspberry Pi GPIOs

Read the blog entry at http://jeremyblythe.blogspot.com for more information
'''
import threading
import time
import RPi.GPIO as GPIO
import ConfigParser
import sys
import os
import signal
from subprocess import call

HIGH = 'high'
LOW = 'low'
FLASH = 'flash'
LOWSHOT = 'lowshot'
HIGHSHOT = 'highshot'

modes = [LOW,HIGH,FLASH,LOWSHOT,HIGHSHOT]
flash_state = HIGH

gpo_lock = threading.Lock()
gpos = {} #Used inside gpo_lock
gpo_keep_running = True #Used inside gpo_lock

gpi_lock = threading.Lock()
gpis = {} #Used inside gpi_lock
gpi_keep_running = True #Used inside gpi_lock

fifo = None
debug = False

def print_debug(msg):
    if debug == True:
        print msg

def update_flash_state():  
    global flash_state          
    if (flash_state == LOW):
        flash_state = HIGH
    else:
        flash_state = LOW


class Gpo():
    """Represents a GPO. Action is called repeatedly to update the state if required (mostly for flashing)."""
    def __init__(self,pin,mode):
        self.pin = pin
        self.mode = mode
        self.state = None
        
        GPIO.setup(self.pin, GPIO.OUT)
        
    def __repr__(self):
        return "Pin=%s, Mode=%s, State=%s" % (self.pin, self.mode, self.state)    
        
    def action(self):
        if (self.mode != self.state):
            if (self.mode == FLASH):
                self.switch(flash_state)
            elif (self.mode == LOWSHOT):
                self.switch(LOW)
                self.mode = HIGH
            elif (self.mode == HIGHSHOT):
                self.switch(HIGH)
                self.mode = LOW
            else:
                self.switch(self.mode)
                
    def switch(self, new_state):
        print_debug("Switching GPO %s %s" % (self.pin, new_state))
        GPIO.output(self.pin, new_state == HIGH)
        self.state = new_state                                           


class Gpi():
    """Represents a GPI. Action is called repeatedly to poll the state and run the command if required"""
    def __init__(self,pin,command):
        self.pin = pin
        self.command = command
        self.state = None
        
        GPIO.setup(self.pin, GPIO.IN)
        
    def __repr__(self):
        return "Pin=%s, Command=%s, State=%s" % (self.pin, self.command, self.state)    
        
    def action(self):
        new_state = GPIO.input(self.pin)
        if (new_state != self.state):
            self.state = new_state
            if self.state == True:
                call(self.command, shell=True)                                          


class GpoThread(threading.Thread):
    """Thread to continuously update the state of the GPOs (if required). Most useful for flashing."""
    def run(self):        
        while True:
            update_flash_state()
            with gpo_lock:
                if gpo_keep_running == False:
                    break
                print_debug(gpos)
                for gpo in gpos.values():
                    gpo.action()
            time.sleep(0.25)
        print_debug('GPO thread stopped')


class GpiThread(threading.Thread):
    """Thread to continuously read the state of each gpi in turn"""
    def run(self):
        while True:
            with gpi_lock:
                if gpi_keep_running == False:
                    break
                for gpi in gpis.values():
                    gpi.action()
            time.sleep(0.1)    
        print_debug('GPI thread stopped')            


def setup(config_file_path):
    """Setup from the config file"""
    # Load config
    config = ConfigParser.ConfigParser()
    config.read(config_file_path)
    global debug
    debug = config.getboolean('options', 'debug')
    global fifo
    fifo = config.get('gpos', 'fifo')
    for name,cfg in config.items('gpo_pins'):
        tokens = cfg.split(',',1)
        pin = tokens[0].strip()
        initial_mode = tokens[1].strip().lower()
        if not initial_mode in modes:
            exit('%s is not a valid mode' % initial_mode)        
        gpos[name] = Gpo(int(pin),initial_mode)
    for name,cfg in config.items('gpi_pins'):
        tokens = cfg.split(',',1)
        pin = tokens[0].strip()
        cmd = tokens[1].strip()
        if cmd[-1] != '&':
            cmd += ' &'
        gpis[name] = Gpi(int(pin),cmd)
        
def read_fifo():
    """Blocking fifo reader"""    
    #Make the fifo
    if os.path.exists(fifo):  
        os.remove(fifo)
    os.mkfifo(fifo)
    os.chmod(fifo,0666)
    f = open(fifo,'r+')
    s = ''
    while s != 'STOP':
        s = f.readline().strip()
        tokens = s.split()
        if (len(tokens) > 1 and tokens[0] in gpos and tokens[1] in modes):
            print_debug('Accepted: %s' % tokens)
            with gpo_lock:
                gpos[tokens[0]].mode = tokens[1]
        else:
            print_debug('Rejected: %s' % tokens)
    f.close()
    #Delete the fifo
    os.remove(fifo)
    print_debug('FIFO reader stopped')
    
def terminate_threads():    
    """Graceful thread termination"""
    global gpo_keep_running
    global gpi_keep_running
    with gpo_lock: 
        gpo_keep_running = False
    with gpi_lock:
        gpi_keep_running = False
    
def signal_handler(signal, frame):
    """Signal handler to send the poison pill to the fifo"""
    with open(fifo,'w') as f:
        f.write('STOP\n')
    
if __name__ == '__main__':
    try:
        if len(sys.argv) < 2:
            exit('GPIO service - provides simple management of Raspberry Pi GPIOs\n   by Jeremy Blythe (http://jeremyblythe.blogspot.com)\n\n   Usage: gpioservice.py {config-file-path}')
        cfg_path = sys.argv[1]    
        if not os.path.exists(cfg_path):
            exit('Config file does not exist [%s]' % cfg_path)  
        setup(cfg_path)
        # Trap SIGINT (Ctrl-C) and exit cleanly
        signal.signal(signal.SIGINT, signal_handler)  
        # Start the Gpo management thread to control flashing etc.
        GpoThread().start()                
        # Start the Gpi management thread to run commands
        GpiThread().start()   
        # Start the fifo blocking read loop
        read_fifo()    
        # Signal graceful thread termination
        terminate_threads()
    except Exception as e:
        terminate_threads()    
