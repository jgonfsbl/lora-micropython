from time import sleep
from machine import Pin, I2C
from ssd1306 import SSD1306_I2C


def send(lora):
    i2c = I2C(-1, Pin(22), Pin(21))
    oled = SSD1306_I2C(128, 64, i2c)
    
    counter = 0
    print("***********")
    print("LoRa Sender")
    print("***********")
    
    while True:
        payload = '[{}]'.format(counter)
        print("Sending packet: \n{}\n".format(payload))
        oled.fill(0)
        oled.text(">>>LoRa TX<<<", 0, 0)
        oled.text("DATA= {}".format(payload), 0, 10)
        oled.text("RSSI= {}".format(lora.packetRssi()), 0, 20)
        
        oled.show()
        lora.println(payload)
        counter += 1
        sleep(5)        

