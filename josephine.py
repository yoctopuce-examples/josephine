#!/usr/bin/python
# -*- coding: utf-8 -*-
import os, sys

# add ../../Sources to the PYTHONPATH
from yoctopuce.yocto_api import *
from yoctopuce.yocto_relay import *
from yoctopuce.yocto_buzzer import *
from yoctopuce.yocto_proximity import *
from yoctopuce.yocto_led import *


class CoffeeMachine(object):
    OFF = 0
    HEATING = 1
    READY = 2
    DISPENSING = 3
    WAITING_PICKUP = 4
    CUP_MISSALIGNED = 5

    def __init__(self, proximity, relay_power, relay_coffee, buzzer, led_red, led_green):
        """

        :type proximity: YProximity
        :type relay_power: YRelay
        :type relay_coffee: YRelay
        :type buzzer: YBuzzer
        :type led_red: YLed
        :type led_green: YLed
        """
        super().__init__()
        self.tm = datetime.datetime.now()
        self.proximity = proximity
        self.relay_power = relay_power
        self.relay_coffee = relay_coffee
        self.buzzer = buzzer
        self.led_red = led_red
        self.led_green = led_green
        self.state = None
        self._set_ready_state()

    def updateProximity(self, value):
        if not self.relay_coffee.isOnline() or not self.relay_power.isOnline():
            reportError("No relay detected. Please setup the logical name of the relays")
            return
        if self.state == self.READY or self.state == self.CUP_MISSALIGNED:
            if value >= 1000:
                self._set_ready_state()
                return
            if 400 < value < 800:
                # cup present
                self.relay_coffee.pulse(200)
                self._set_dispensing_state()
            else:
                self._set_missaligned_state()
        elif self.state == self.DISPENSING:
            if value >= 1000:
                self._set_ready_state()
                return
            if value < 400 or value > 800:
                self._set_missaligned_state()

    def _set_ready_state(self):
        if self.state != self.READY:
            print("switch to state READY")
            self.tm = datetime.datetime.now()
            self.state = self.READY
            self.buzzer.set_volume(0)
            led_green.set_blinking(YLed.BLINKING_RELAX)
            self.led_red.set_power(YLed.POWER_OFF)
            self.led_green.set_power(YLed.POWER_ON)

    def _set_missaligned_state(self):
        if self.state != self.CUP_MISSALIGNED:
            print("switch to state CUP_MISSALIGNED")
            self.tm = datetime.datetime.now()
            self.state = self.CUP_MISSALIGNED
            self.buzzer.set_volume(50)
            self.buzzer.set_frequency(750)  # fixme use sequence
            led_red.set_blinking(YLed.BLINKING_RELAX)
            self.led_red.set_power(YLed.POWER_ON)
            self.led_green.set_power(YLed.POWER_OFF)

    def _set_dispensing_state(self):
        if self.state != self.DISPENSING:
            print("switch to state DISPENSING")
            self.tm = datetime.datetime.now()
            self.state = self.DISPENSING
            self.buzzer.set_volume(0)
            led_red.set_blinking(YLed.BLINKING_STILL)
            self.led_red.set_power(YLed.POWER_ON)
            self.led_green.set_power(YLed.POWER_OFF)

    def _set_pickup_state(self):
        if self.state != self.WAITING_PICKUP:
            print("switch to state WAITING_PICKUP")
            self.tm = datetime.datetime.now()
            self.state = self.WAITING_PICKUP
            self.buzzer.set_volume(100)
            self.buzzer.set_frequency(750)  # fixme use sequence
            led_red.set_blinking(YLed.BLINKING_AWARE)
            self.led_red.set_power(YLed.POWER_OFF)
            self.led_green.set_power(YLed.POWER_ON)

    def periodicUpdate(self):
        if self.state == self.DISPENSING:
            now = datetime.datetime.now()
            delta = now - self.tm
            if delta.total_seconds() > 60:
                self._set_pickup_state()


def reportError(msg):
    now = datetime.datetime.now()
    timestr = now.strftime("[%y-%m-%d %H:%M:%S]")
    print(timestr + msg)


def functionValueChangeCallback(fct, value_str):
    value = int(value_str)
    print("Proximity: " + value_str)
    global coffee_machine
    coffee_machine.updateProximity(value)


errmsg = YRefParam()

# No exception please
YAPI.DisableExceptions()

# Setup the API to use local USB devices
if YAPI.RegisterHub("192.168.1.52", errmsg) != YAPI.SUCCESS:
    sys.exit("init error" + errmsg.value)

if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
    sys.exit("init error" + errmsg.value)

proximity = YProximity.FirstProximity()
if proximity is None:
    sys.exit("No Yocto-Proximity found")
relay_power = YRelay.FindRelay("power")
if not relay_power.isOnline():
    sys.exit("No relay with logical name \"power\" found")

relay_coffee = YRelay.FindRelay("coffee")
if not relay_coffee.isOnline():
    sys.exit("No relay with logical name \"coffee\" found")

buzzer = YBuzzer.FirstBuzzer()
if buzzer is None:
    sys.exit("No Yocto-Buzzer found")
buzzer_serial = buzzer.get_module().get_serialNumber()
led_red = YLed.FindLed(buzzer_serial + ".led2")
led_green = YLed.FindLed(buzzer_serial + ".led1")

coffee_machine = CoffeeMachine(proximity, relay_power, relay_coffee, buzzer, led_red, led_green)
proximity.registerValueCallback(functionValueChangeCallback)

print('Hit Ctrl-C to Stop ')

while True:
    YAPI.UpdateDeviceList(errmsg)  # traps plug/unplug events
    YAPI.Sleep(1000, errmsg)  # traps others events
    coffee_machine.periodicUpdate()
