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


class BuildingAnimation(BaseStripAnim):
    """Build status is 'building' animation"""

    def __init__(self, led, color, base_color, tail=4, start=0, end=-1):
        super(BuildingAnimation, self).__init__(led, start, end)
        self._color = color
        self._base_color = base_color

        self._tail = tail + 1  # makes tail math later easier
        if self._tail >= self._size / 2:
            self._tail = (self._size / 2) - 1

        self._direction = -1
        self._last = 0
        self._fadeAmt = 256 / self._tail

    def step(self, amt = 1):
        self._led.all_off() # leds will glow trailing color w/o this

        self._last = self._start + self._step
        self._led.set(self._last, self._color)

        for i in range(74):
                self._led.set(i, self._base_color)
                self.masterBrightness = i

        for i in range(self._tail):
            # head and trailing faded tails
            self._led.set(self._last - i, colors.color_scale(self._color, 255 - (self._fadeAmt * i)))
            self._led.set(self._last + i, colors.color_scale(self._color, 255 - (self._fadeAmt * i)))

        if self._start + self._step >= self._end:
            self._direction = -self._direction
        elif self._step <= 0:
            self._direction = -self._direction

        self._step += self._direction * amt


class LedPatterns(threading.Thread):
    """Changes LED Patterns based on Jenkins status"""
    def __init__(self, queue):
        self.led = led
        self.queue = queue
        self.failure_colors = [colors.Red, colors.DarkRed]
        self.failed_base_color = colors.Red
        self.success_base_color = colors.Green
        self.aborted_base_color = colors.SlateGray
        self.building_color = colors.Gold
        threading.Thread.__init__(self)

    def run(self):
        while True:
            if not self.queue.empty():
                previous_build_status = self.queue.get()[0]
                currently_building = self.queue.get()[1]


                #     elif previous_build_status == 'FAILURE':
                #         anim = BuildingAnimation(self.led, color=self.building_color, base_color=self.failed_base_color)
                #         anim.run(fps=50)

                #     elif previous_build_status == 'ABORTED':
                #         anim = BuildingAnimation(self.led, color=self.building_color, base_color=self.aborted_base_color)
                #         anim.run(fps=50)

                # elif not currently_building:
                #     if previous_build_status == 'SUCCESS':
                #         self.led.fill(self.success_base_color)
                #         self.led.update()

                #     if previous_build_status == 'FAILURE':
                #         self.led.fill(self.failed_base_color)
                #         self.led.update()

                #     elif previous_build_status == 'ABORTED':
                #         self.led.fill(self.aborted_base_color)
                #         self.led.update()

# class SuccessBuildingPattern(threading.Thread):
#     """Success while Building Pattern"""
#     def __init__(self, queue):
#         self.led = led
#         self.queue = queue
#         self.failure_colors = [colors.Red, colors.DarkRed]
#         self.failure_base_color = colors.Red
#         self.success_base_color = colors.Green
#         self.aborted_base_color = colors.SlateGray
#         self.building_color = colors.Gold
#         threading.Thread.__init__(self)

#     def run(self):
#         while True:
#             if not self.queue.empty():
#                 previous_build_status = self.queue.get()[0]
#                 currently_building = self.queue.get()[1]

#                 if currently_building:
#                     if previous_build_status == 'SUCCESS':
#                         anim = BuildingAnimation(self.led, color=self.building_color, base_color=self.success_base_color)
#                         anim.run(fps=50)
#                 time.sleep(.5)


# class FailureBuildingPattern(threading.Thread):
#     """Failure while Building Pattern"""
#     def __init__(self, queue):
#         self.led = led
#         self.queue = queue
#         self.failure_colors = [colors.Red, colors.DarkRed]
#         self.failure_base_color = colors.Red
#         self.success_base_color = colors.Green
#         self.aborted_base_color = colors.SlateGray
#         self.building_color = colors.Gold
#         threading.Thread.__init__(self)

#     def run(self):
#         while True:
#             if not self.queue.empty():
#                 previous_build_status = self.queue.get()[0]
#                 currently_building = self.queue.get()[1]

#                 if currently_building:
#                     if previous_build_status == 'FAILURE':
#                         anim = BuildingAnimation(self.led, color=self.building_color, base_color=self.failed_base_color)
#                         anim.run(fps=50)
#                 time.sleep(.5)


class FailurePattern(threading.Thread):
    """Failure not building Pattern"""
    def __init__(self, queue):
        self.led = led
        self.queue = queue
        self.failure_colors = [colors.Red, colors.DarkRed]
        self.failure_base_color = colors.Red
        self.success_base_color = colors.Green
        self.aborted_base_color = colors.SlateGray
        self.building_color = colors.Gold
        threading.Thread.__init__(self)

    def run(self):
        while True:
            previous_build_status = self.queue.get()[0]
            currently_building = self.queue.get()[1]

            if currently_building == False:
                if previous_build_status == 'FAILURE':
                    self.led.fill(self.failure_base_color)
                    self.led.update()
            time.sleep(.1)


class SuccessPattern(threading.Thread):
    """Success not building Pattern"""
    def __init__(self, queue):
        self.led = led
        self.queue = queue
        self.failure_colors = [colors.Red, colors.DarkRed]
        self.failure_base_color = colors.Red
        self.success_base_color = colors.Green
        self.aborted_base_color = colors.SlateGray
        self.building_color = colors.Gold
        threading.Thread.__init__(self)

    def run(self):
        while True:
            previous_build_status = self.queue.get()[0]
            currently_building = self.queue.get()[1]

            if currently_building == False:
                if previous_build_status == 'SUCCESS':
                    self.led.fill(self.success_base_color)
                    self.led.update()
            time.sleep(.1)

class AbortedPattern(threading.Thread):
    """Aborted not building Pattern"""
    def __init__(self, queue):
        self.led = led
        self.queue = queue
        self.failure_colors = [colors.Red, colors.DarkRed]
        self.failure_base_color = colors.Red
        self.success_base_color = colors.Green
        self.aborted_base_color = colors.SlateGray
        self.building_color = colors.Gold
        threading.Thread.__init__(self)

    def run(self):
        while True:
            previous_build_status = self.queue.get()[0]
            currently_building = self.queue.get()[1]

            if currently_building == False:
                if previous_build_status == 'ABORTED':
                    self.led.fill(self.aborted_base_color)
                    self.led.update()
            time.sleep(.1)


class BuildingPattern(threading.Thread):
    """Building Pattern"""
    def __init__(self, queue):
        self.led = led
        self.queue = queue
        self.failure_colors = [colors.Red, colors.DarkRed]
        self.failure_base_color = colors.Red
        self.success_base_color = colors.Green
        self.aborted_base_color = colors.SlateGray
        self.building_color = colors.Gold
        threading.Thread.__init__(self)

    def run(self):
        while True:
            previous_build_status = self.queue.get()[0]
            currently_building = self.queue.get()[1]

            if currently_building == True:
                self.led.fill(self.building_color)
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

            # self.previous_build_number = job.get_last_buildnumber()
            # print "Last completed build number %s" % self.previous_build_number

            previous_build_status = previous_build.get_status()
            # print "Last completed build status %s" % previous_build_status

            # Determine if there's a build building
            currently_building = self.job.is_running()
            # print "Job is currently building: %s" % currently_building

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
    # jenkins_status.setDaemon(True)

    led_patterns = LedPatterns(queue)
    # led_patterns.setDaemon(True)

    # success_building_pattern = SuccessBuildingPattern(queue)
    # failure_building_pattern = FailureBuildingPattern(queue)
    success_pattern = SuccessPattern(queue)
    building_pattern = BuildingPattern(queue)
    failure_pattern = FailurePattern(queue)
    aborted_pattern = AbortedPattern(queue)

    print "Starting Jenkins Status Reader"
    jenkins_status.start()

    # print "Starting leds"
    # led_patterns.start()

    # print "Starting Success Building pattern"
    # success_building_pattern.start()

    # print "Starting Failure Building pattern"
    # failure_building_pattern.start()

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
