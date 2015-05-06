#!/usr/bin/env python

import colorsys
import json
import optparse
import os
import pprint
import random
import shutil
import signal
import sys
import threading
import time
import traceback
import Queue

from jenkinsapi.jenkins import Jenkins
from bibliopixel.animation import BaseStripAnim
from bibliopixel.drivers.LPD8806 import DriverLPD8806
from bibliopixel.drivers.driver_base import ChannelOrder
from bibliopixel.led import *
import bibliopixel.colors as colors


driver = DriverLPD8806(74, c_order=ChannelOrder.GRB, SPISpeed=2)
led = LEDStrip(driver)

# Global colors
failure_colors = [colors.Red, colors.DarkRed]
failed_base_color = colors.Red
success_base_color = colors.Green
aborted_base_color = colors.SlateGray
building_color = colors.Gold


def parse_args():
    """Parses args"""
    parser = optparse.OptionParser()
    parser.add_option("", "--jenkins-url",
                      help="Base url of your jenkins server (ie: https://jenkins.example.com")
    parser.add_option("", "--job",
                      help="Job for build light to monitor")

    (opts, args) = parser.parse_args()

    if not opts.jenkins_url and opts.job:
        print >> sys.stderr, "Please specify a jenkins url and job"
        sys.exit(2)

    return opts


class FailurePattern(threading.Thread):
    """Failure not building Pattern"""
    def __init__(self, queue):
        self.led = led
        self.queue = queue
        threading.Thread.__init__(self)

    def run(self):
        while True:
            previous_build_status = self.queue.get()[0]
            currently_building = self.queue.get()[1]

            if currently_building == False:
                if previous_build_status == 'FAILURE':
                    self.led.fill(failure_base_color)
                    self.led.update()
            time.sleep(.1)


class SuccessPattern(threading.Thread):
    """Success not building Pattern"""
    def __init__(self, queue):
        self.led = led
        self.queue = queue
        threading.Thread.__init__(self)

    def run(self):
        while True:
            previous_build_status = self.queue.get()[0]
            currently_building = self.queue.get()[1]

            if currently_building == False:
                if previous_build_status == 'SUCCESS':
                    self.led.fill(success_base_color)
                    self.led.update()
            time.sleep(.1)

class AbortedPattern(threading.Thread):
    """Aborted not building Pattern"""
    def __init__(self, queue):
        self.led = led
        self.queue = queue
        threading.Thread.__init__(self)

    def run(self):
        while True:
            previous_build_status = self.queue.get()[0]
            currently_building = self.queue.get()[1]

            if currently_building == False:
                if previous_build_status == 'ABORTED':
                    self.led.fill(aborted_base_color)
                    self.led.update()
            time.sleep(.1)


class BuildingPattern(threading.Thread):
    """Building Pattern"""
    def __init__(self, queue):
        self.led = led
        self.queue = queue
        threading.Thread.__init__(self)

    def run(self):
        while True:
            previous_build_status = self.queue.get()[0]
            currently_building = self.queue.get()[1]

            if currently_building == True:
                self.led.fill(building_color)
                self.led.update()
            time.sleep(.1)


class JenkinsStatus(threading.Thread):
    def __init__(self, job, queue):
        self.job = job
        self.queue = queue
        threading.Thread.__init__(self)

    def run(self):

        while True:

            # Determine last completed build
            previous_build = self.job.get_last_completed_build()
            previous_build_status = previous_build.get_status()

            # Determine if there's a build building
            currently_building = self.job.is_running()

            # Add jenkins statuses to the queue
            self.queue.put((previous_build_status, currently_building))

            time.sleep(.1)


def ctrlc(signal, frame):
    print "Exiting . . ."
    led.all_off()
    led.update()
    sys.exit(0)


def main():
    opts = parse_args()
    server = Jenkins(opts.jenkins_url)
    job = server[(opts.job)]

    queue = Queue.Queue()

    led.all_off()
    led.update()

    # Override ctrl-c to kill threads
    queue = Queue.Queue()

    jenkins_status = JenkinsStatus(job, queue)

    led_patterns = LedPatterns(queue)

    success_pattern = SuccessPattern(queue)
    building_pattern = BuildingPattern(queue)
    failure_pattern = FailurePattern(queue)
    aborted_pattern = AbortedPattern(queue)

    print "Starting Jenkins Status Reader"
    jenkins_status.start()
    time.sleep(1)

    print "Starting Success pattern"
    success_pattern.start()

    print "Starting Building pattern"
    building_pattern.start()

    print "Starting Failure pattern"
    failure_pattern.start()

    print "Starting Aborted pattern"
    aborted_pattern.start()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, ctrlc)
    main()
