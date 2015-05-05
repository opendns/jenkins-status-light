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

# import pdb

from jenkinsapi.jenkins import Jenkins
from bibliopixel.animation import BaseStripAnim
from bibliopixel.drivers.LPD8806 import DriverLPD8806
from bibliopixel.drivers.driver_base import ChannelOrder
from bibliopixel.led import *
import bibliopixel.colors as colors

# Globals
num_leds = 74
colors = {'r': 0, 'g': 0, 'b': 0, 'v': 1.0}
red = {'r': 255, 'g': 0, 'b': 0, 'v': 1.0}
yellow = {'r': 255, 'g': 215, 'b': 0, 'v': 1.0}
green = {'r': 0, 'g': 255, 'b': 0, 'v': 1.0}
white = {'r': 150, 'g': 150, 'b': 150, 'v': 1.0}
previous_build = None
previous_build_status = None

random.seed(time.time())

driver = DriverLPD8806(74, c_order=ChannelOrder.GRB, SPISpeed=2)
led = LEDStrip(driver)


def parse_args():
    """Parses args"""
    parser = optparse.OptionParser()
    parser.add_option("", "--jenkins-url",
                      help="Base url of your jenkins server (ie: https://jenkins.example.com")
    parser.add_option("", "--job",
                      help="Job for build light to monitor")
    parser.add_option("", "--prefix", default="jenkins",
                      help="Graphite metric prefix")

    (opts, args) = parser.parse_args()

    if not opts.jenkins_url:
        print >> sys.stderr, "Please specify a jenkins url"
        sys.exit(1)

    return opts


class Brightness(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.sleep_time = 0.1

    def run(self):
        while True:
            for i in range(0, 100):
                colors['v'] = i * 0.01
                self.refresh_dict()
                time.sleep(self.sleep_time)
            for i in range(100, -1, -1):
                colors['v'] = i * 0.01
                self.refresh_dict()
                time.sleep(self.sleep_time)

    def refresh_dict(self):
        if 'brightness_slider' in output_dict:
            self.sleep_time = float(output_dict['brightness_slider']) * 0.01

class Leds(threading.Thread):
    def __init__(self):
        self.strip = LPD8806.strand(leds=num_leds)
        self.queue = queue
        self.sleep_time = 0.1
        threading.Thread.__init__(self)

    def run(self):
        while True:

            try:
                if self.currently_building:
                    if self.previous_build_status == 'SUCCESS':
                        Pattern(green).run()

                    elif self.previous_build_status == 'FAILURE':
                        Pattern(red).run()

                    elif self.previous_build_status == 'ABORTED':
                        Pattern(yellow).run()

                elif not self.currently_building:
                    if self.previous_build_status == 'SUCCESS':
                        Pattern(green).run()

                    if self.previous_build_status == 'FAILURE':
                        Pattern(red).run()

                    elif self.previous_build_status == 'ABORTED':
                        Pattern(yellow).run()

            except KeyboardInterrupt:
                led.all_off()
                led.update()


class Pattern(threading.Thread):
    def __init__(self, color):
        self.color = color
        self.strip = led
        self.sleep_time = 0.1
        self.choice = 'FaderTail'
        self.valid_choices = ['Fader',
                              'FadeTail',
                              'SingleTail']
        threading.Thread.__init__(self)

    def run(self):
        while True:
            self.refresh_dict()
            if self.choice == 'Fader':
                self.fader()
            elif self.choice == 'FadeTail':
                self.fade_tail()
            elif self.choice == 'SingleTail':
                self.mover()
            else:
                self.black_out()
                self.mover()
                self.black_out()

    def refresh_dict(self):
        button = str(output_dict['pattern_button'])
        self.sleep_time = float(int(output_dict['pattern_slider'])) * 0.00001
        if button in self.valid_choices:
            self.choice = button

    def black_out(self):
        self.strip.fill((0, 0, 0), start=0, end=num_leds)
        self.strip.update()
        time.sleep(0.1)

    def white_out(self):
        self.strip.fill((150, 150, 150), start=0, end=num_leds)
        self.strip.update()
        time.sleep(0.1)

    def fade_tail(self):

        def build(led, pos, diff):
            if led['led'] + 1 > num_leds - 1:
                led['led'] = 0
            else:
                led['led'] += 1
            for i in ['r', 'g', 'b']:
                led[i] = colors[i] - (diff * pos)
                if led[i] < diff:
                    led[i] = 0
            return led

        group = []
        tail = int(0.50 * num_leds)
        diff = int((255 / tail) + 2)

        # build structure
        for i in range(0, tail):
            group.append({'led': num_leds - i,
                          'r': 0,
                          'g': 0,
                          'b': 0})

        for head in range(0, num_leds):
            self.refresh_dict()
            for j in range(0, tail):
                led = build(group[j], j, diff)
                print led
                self.strip.set(led['led'], (led['r'], led['g'], led['b']))
                group[j] = led
            self.strip.update()
            time.sleep(self.sleep_time)

    def mover(self):
        # Move from beginning to end
        for i in range(0, num_leds):
            if i == 0:
                off = num_leds - 1
            else:
                off = i - 1
            self.strip.set(off, (0, 0, 0))
            self.strip.set(i, (colors['r'], colors['g'], colors['b']))
            self.strip.update()
            self.refresh_dict()
            time.sleep(self.sleep_time)

        # Move from end to beginning
        for i in range(num_leds - 1, -1, -1):
            if i == num_leds - 1:
                off = 0
            else:
                off = i + 1
            self.strip.set(off, (0, 0, 0))
            self.strip.set(i, (colors['r'], colors['g'], colors['b']))
            self.strip.update()
            self.refresh_dict()
            time.sleep(self.sleep_time)

    def fader(self):
        self.strip.fill((colors['r'], colors['g'], colors['b']), start=0, end=num_leds)
        self.strip.update()
        self.refresh_dict()
        time.sleep(self.sleep_time)

        def build_led():
            steps = 50
            led = {'led': random.randint(0, num_leds - 1),
                   'r': 0,
                   'g': 0,
                   'b': 0,
                   'r_max': random.randint(1, 254),
                   'g_max': random.randint(1, 254),
                   'b_max': random.randint(1, 254),
                   'dir': 1,
                   'count': 0}

            led['max_val'] = max(led['r_max'], led['g_max'], led['b_max']) + 3
            if led['max_val'] > 254:
                led['max_val'] = 255
            led['r_dec'] = led['r_max'] / steps
            led['g_dec'] = led['g_max'] / steps
            led['b_dec'] = led['b_max'] / steps
            #if led['r'] < 200 and led['g'] < 200 and led['b'] < 200:
            #    v = random.sample(['r', 'g', 'b'], 1)
            #    led[v[0]] = random.randint(200, 255)
            print led
            return led

        leds = []
        self.strip.fill(0, 0, 0, start=0, end=num_leds)
        self.strip.update()

        for i in range(0, num_leds / 2):
            led = build_led()
            leds.append(led)

        while True:
            for i in range(0, len(leds)):
                led = leds[i]
                if led['dir'] > 0:
                    if (led['count'] * led['r_dec']) % led['r_max'] == 0:
                        led['r'] += 1
                    if led['count'] % led['g_dec'] == 0:
                        led['g'] += 1
                    if led['count'] % led['b_dec'] == 0:
                        led['b'] += 1
                else:
                    if led['count'] % led['r_dec'] == 0:
                        led['r'] -= 1
                    if led['count'] % led['g_dec'] == 0:
                        led['g'] -= 1
                    if led['count'] % led['b_dec'] == 0:
                        led['b'] -= 1

                led['count'] += 1

                if (led['r'] >= led['max_val'] or
                            led['g'] >= led['max_val'] or
                            led['b'] >= led['max_val']):
                    led['dir'] = -1
                    led['count'] = 0

                if (led['r'] <= 0 and
                            led['g'] <= 0 and
                            led['b'] <= 0):
                    leds[i] = build_led()
                    led = leds[i]

                self.strip.set(led['led'], led['r'], led['g'], led['b'])
                leds[i] = led
            self.strip.update()
            time.sleep(0.005)


class ColorChanger(threading.Thread):
    def __init__(self):
        self.sleep_time = 0.2
        self.choice = 'white'
        threading.Thread.__init__(self)

    @staticmethod
    def set_color():
        colors['r'] = output_dict['r']
        colors['g'] = output_dict['g']
        colors['b'] = output_dict['b']

    def run(self):
        while True:
            self.refresh_dict()
            if 'color_button' in output_dict:
                if self.choice == 'rainbow':
                    self.rainbow()
                elif self.choice == 'white':
                    output_dict['r'] = 200
                    output_dict['g'] = 200
                    output_dict['b'] = 200
                    self.set_color()
                elif self.choice == 'black':
                    self.set_color()
                elif self.choice == 'solid':
                    self.set_color()
            time.sleep(self.sleep_time)

    def refresh_dict(self):
        global output_dict
        self.choice = output_dict['color_button']
        speed = float(output_dict['hue_slider']) * 0.00001
        if speed > 1 and self.choice == 'rainbow':
            self.sleep_time = speed
            print speed
        else:
            self.sleep_time = 0.1

    def rainbow(self):
        for i in range(0, 360):
            self.refresh_dict()

            if 'saturation_slider' in output_dict:
                sat = float(output_dict['saturation_slider']) / 255.000
            else:
                sat = 1.000
            if 'brightness_slider' in output_dict:
                bright = float(output_dict['brightness_slider']) / 255.000
            else:
                bright = 1.000

            (r, g, b) = colorsys.hsv_to_rgb(float(i) / 360, sat, bright)
            r = int(r * 255)
            g = int(g * 255)
            b = int(b * 255)
            colors['r'] = r
            colors['g'] = g
            colors['b'] = b
            self.refresh_dict()
            if 'color_button' in output_dict:
                if output_dict['color_button'] != 'rainbow':
                    return
            time.sleep(self.sleep_time)

        for i in range(359, -1, -1):
            self.refresh_dict()

            if 'saturation_slider' in output_dict:
                sat = float(output_dict['saturation_slider']) / 255.000
            else:
                sat = 1.0
            if 'brightness_slider' in output_dict:
                bright = float(output_dict['brightness_slider']) / 255.000
            else:
                bright = 1.000

            (r, g, b) = colorsys.hsv_to_rgb(float(i) / 360, sat, bright)
            r = int(r * 255)
            g = int(g * 255)
            b = int(b * 255)
            colors['r'] = r
            colors['g'] = g
            colors['b'] = b
            self.refresh_dict()
            if 'color_button' in output_dict:
                if output_dict['color_button'] != 'rainbow':
                    return
            time.sleep(self.sleep_time)


class JenkinsStatus(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        opts = parse_args()
        server = Jenkins(opts.jenkins_url)
        job = server[(opts.job)]

        while True:
            self.refresh_input()
            time.sleep(0.25)

            # Determine last completed build
            previous_build = job.get_last_completed_build()

            self.previous_build_number = job.get_last_buildnumber()
            print "Last completed build number %s" % self.previous_build_number

            self.previous_build_status = previous_build.get_status()
            print "Last completed build status %s" % self.previous_build_status

            # Determine if there's a build building
            self.currently_building = job.is_running()
            print "Job is currently building: %s" % self.currently_building

    def refresh_input(self):
        global output_dict
        lock = threading.Lock()

        lock.acquire()

        try:
            pass
        except Exception, e:
            print "============ EXCEPTION ============"
            print "%s" % e
            print traceback.format_exc()
            print "==================================="
        finally:
            lock.release()

class SocketInput(threading.Thread):
    def __init__(self, port=9999):
        pass
    def run(self):
        while True:
            time.sleep(1)

def ctrlc(signal, frame):
    print "Exiting . . ."
    os._exit(0)

def main():
    """Main function"""
    print ("Bootup may take up to 10 seconds as threads must "
           "start in order and sequentially.")

    # Override ctrl-c to kill threads
    signal.signal(signal.SIGINT, ctrlc)
    queue = Queue.Queue()

    jenkins_status = JenkinsStatus()
    brightness = Brightness()
    # leds = Pattern(red)

    print "Starting Jenkins Status Reader"
    jenkins_status.start() # Starts the thread once object is created
    time.sleep(1)

    print "Starting Brightness"
    brightness.start() # Starts the thread
    time.sleep(1)

    # print "Starting leds"
    # leds.start()

    sys.exit(0)

if __name__ == "__main__":
    main()
