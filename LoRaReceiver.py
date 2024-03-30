from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
from gfx import GFX
import time
import math


def data(payload):
    stringa = payload.decode()
    tupla = stringa.split(",")
    return tupla

def receive(lora):
    i2c = I2C(-1, Pin(22), Pin(21))
    oled = SSD1306_I2C(128, 64, i2c)
    graphics = GFX(128, 64, oled.pixel)
    oled.fill(0)
    oled.text("WAIT SIGNAL...", 0, 0)
    oled.show()
    
    while True:
        if lora.receivedPacket():
            lora.blink_led()
            
            try:
                payload = lora.read_payload()
                a = data(payload)
                oled.fill(0)
                d = time.localtime()
                s = "RXT={}/{}@{}:{}".format(d[1], d[2], d[3], d[4])
                oled.text(s, 0, 0)
                oled.text("POD_ID={} TEMP={}".format(a[0], a[1]), 0, 10)
                oled.text("RSSI= {}".format(lora.packetRssi()), 0, 20)
                oled.text("S1={},{}".format(a[2], a[4]), 0, 30)
                oled.text("S2={},{}".format(a[3], a[5]), 0, 40)
                oled.text("V={:>4}, I={}".format(a[6], a[7]), 0, 50)
                graphics.rect(84, 30, 20, 8, 1)
                offset = int(a[2]) * 2
                
                if offset <= 0:
                    offset = 0
                elif offset >= 16:
                    offset = 6

                graphics.fill_rect(86, 32, offset, 4, 1)        
                graphics.rect(84, 40, 20, 8, 1)
                offset = int(a[3]) * 2
                
                if offset <= 0:
                    offset = 0
                elif offset >= 16:
                    offset = 6

                graphics.fill_rect(86, 42, offset, 4, 1)

                oled.show()
            
            except Exception as e:
                print(e)
            try:        
                print("{}".format(payload.decode()))
            except 'TypeError':
                print("ERORE:")
                print(payload)
