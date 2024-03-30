import gc
import config_lora
from sx127x import SX127x
from controller_esp32 import ESP32Controller
from time import sleep, sleep_ms
from machine import Pin, ADC, I2C, PWM, deepsleep
from onewire import OneWire
from ds18x20 import DS18X20
from ina219 import INA219
from random import seed, randint

gc.collect()

POD_ID = '5' # pod identifier
SEED = 5 # random seed number. We will select the same as the pod number
RETRIES = 3 # number of retries for sending out the lora payload
MAXDELAY = 10000 # time window for sending out lora payload, in milliseconds
N_READINGS = 5 # Number of sensor readings to average on
OLED_ON = False # Enables the embedded OLED display

# Using GPIO pins 2 and 4 as moisture sensor on-demand power supply.
# GPIO pins should be able to provide enough current (current x-sensor demand=10mA, supply 12-40mA max in theory)
PWR_PIN_S1 = 2
PWR_PIN_S2 = 4

DEEP_SLEEP_TIME_1 = 4 * 60 * 60 * 1000 # sleep 4 hours
DEEP_SLEEP_TIME_2 = 24 * 60 * 60 * 1000 # sleep 24 hours
DEEP_SLEEP_TIME_3 = 48 * 60 * 60 * 1000 # sleep 48 hours
 
BATTERY_LOW_VOLTAGE_2 = 3.7 
BATTERY_LOW_VOLTAGE_3 = 3.6

print('=========')
print('POD_ID: {}'.format(POD_ID))
print('=========')

if OLED_ON:
    from ssd1306 import SSD1306_I2C

seed(SEED) # set randomness seed

#initialize controller and LoRa network
controller = ESP32Controller()
lora = controller.add_transceiver(SX127x(name = POD_ID),
                                  pin_id_ss = ESP32Controller.PIN_ID_FOR_LORA_SS,
                                  pin_id_RxDone = ESP32Controller.PIN_ID_FOR_LORA_DIO0)

#initialize I2C bus
i2c = I2C(-1, Pin(22), Pin(21))

#initialize OLED display
if OLED_ON:
    dsp = SSD1306_I2C(128, 64, i2c)

#initialize INA219
ina = INA219(0.1, i2c)
ina.configure(ina.RANGE_16V)

battery_voltage = ina.voltage()
print('BATTERY LEVEL: {}'.format(battery_voltage))
if battery_voltage <= BATTERY_LOW_VOLTAGE_3:
    deepsleep(DEEP_SLEEP_TIME_3)

if battery_voltage <= BATTERY_LOW_VOLTAGE_2:
    deep_sleep_time_msec = DEEP_SLEEP_TIME_2
else:
    deep_sleep_time_msec = DEEP_SLEEP_TIME_1

# setup of analog pins, for moisture sensor reaadings
moist_sens_1 = ADC(Pin(32))
moist_sens_2 = ADC(Pin(33))
pwr_pin_S1 = Pin(PWR_PIN_S1, Pin.OUT)
pwr_pin_S2 = Pin(PWR_PIN_S2, Pin.OUT)

# setup of Dallas onewire temperature sensor on Pin 14
dat = Pin(14)

# create OnWire object
ds = DS18X20(OneWire(dat))

# scan for devices on the bus
roms = ds.scan()
print("ONE WIRE DEVICES FOUND: ", roms)

# POWER ON the moisture sensors
pwr_pin_S1.value(True)
pwr_pin_S2.value(True)

# setup analog pin attenuation to 11DB, to allow readings
# of 3.1V maximum
moist_sens_1.atten(ADC.ATTN_11DB)
moist_sens_2.atten(ADC.ATTN_11DB)

# 100%DRY: 2.7V 4095
# 100%WET: 1.2V 0
# useful range: 3500 - 1200

def classify_reading(value):
    ''' map moisture sensor readings to 11 values, 
        for SUPERDRY: 0
        to  SUPERWET: 10
        :params: int, sensor reading output value
        :returns: str'''

    if value in list(range(0, 1410)):
        return '10'
    elif value in list(range(1411, 1620)):
        return '9'
    elif value in list(range(1621, 1830)):
        return '8'
    elif value in list(range(1831, 2040)):
        return '7'
    elif value in list(range(2041, 2250)):
        return '6'
    elif value in list(range(2251, 2460)):
        return '5'
    elif value in list(range(2461, 2670)):
        return '4'
    elif value in list(range(2671, 2880)):
        return '3'
    elif value in list(range(2881, 3090)):
        return '2'
    elif value in list(range(3091, 3300)):
        return '1'
    elif value in list(range(3301, 4095)):
        return '0'
    else:
        return 'X'

def lora_burst(): 
    ''' performs a burst of n consecutive sensor readings
        and averages them, to produce a single output value for each sensor,
        generate a csv string packet and send it as lora payload.
        :params: none
        :returns: none '''
    
    # zeroing readings
    val_moist_sens_1 = 0
    val_moist_sens_2 = 0
    val_temp_sens_0 = 0
    val_volt_ina219 = 0
    val_mamp_ina219 = 0
    
    print("AVERAGING SENSOR READINGS...")
    print("============================")
    print(" S_1  S_2  TEMP VOLT    MAMP")
    print("----------------------------")

    # perform n times sensor readings
    for i in range(N_READINGS):
        sens_1_reading = moist_sens_1.read()
        sens_2_reading = moist_sens_2.read()
        ina219_volt_reading = ina.voltage()
        ina219_mamp_reading = ina.current()
        ina.sleep()
        ds.convert_temp()
        sleep_ms(750) # must wait 750ms for the Dallas sensor to get the data
        
        for rom in roms:    # one-wire protcol requirement
            sens_0_reading = ds.read_temp(rom)

        val_moist_sens_1 += sens_1_reading        
        val_moist_sens_2 += sens_2_reading
        val_temp_sens_0 += sens_0_reading
        val_volt_ina219 += ina219_volt_reading
        val_mamp_ina219 += ina219_mamp_reading

        print("{:>4} {:>4} {:>5.2f} {:>3.2f} {:>6.2f}".format(
            sens_1_reading, 
            sens_2_reading, 
            sens_0_reading,
            ina219_volt_reading, 
            ina219_mamp_reading))

    avg_reading_0 = int(val_temp_sens_0 / N_READINGS)  # TEMP sensor avg reading
    avg_reading_1 = int(val_moist_sens_1 / N_READINGS) # MOIST sensor 1 avg reading
    avg_reading_2 = int(val_moist_sens_2 / N_READINGS)  # MOIST sensor 2 avg reading
    avg_reading_volt = val_volt_ina219 / N_READINGS     # INA219 avg reading
    avg_reading_mamp = val_mamp_ina219 / N_READINGS     # INA219 avg reading
    cls_reading_1 = classify_reading(avg_reading_1)
    cls_reading_2 = classify_reading(avg_reading_2)
    volt = "{:.2f}".format(avg_reading_volt)    # formatting volt value
    mamp = "{:.2f}".format(avg_reading_mamp)    # formatting milliamp value
    # generating csv string payload
    # POD_ID,TEMP,CLASS1,CLASS2,SENS1,SENS2,VOLT,MAMP
    payload = "{},{},{},{},{},{},{},{}".format(
            POD_ID, 
            avg_reading_0, 
            cls_reading_1, 
            cls_reading_2, 
            avg_reading_1, 
            avg_reading_2,
            volt,
            mamp)
    print("============================")
    print("SENDING PAYLOAD: (POD_ID, avg_reading_0, cls_reading_1, cls_reading_2,  avg_reading_1, avg_reading_2, volt, mamp)")
    print(payload)

    if OLED_ON:
        dsp.fill(0)
        dsp.text("POD_ID==>{}".format(POD_ID), 0, 0)
        dsp.text("RSSI={},T={}".format(lora.packetRssi(),avg_reading_0), 0, 10)
        dsp.text("S1={}, {}".format(cls_reading_1, avg_reading_1), 0, 20)
        dsp.text("S2={}, {}".format(cls_reading_2, avg_reading_2), 0, 30)
        dsp.text("VOLT: {} V".format(volt), 0, 40)
        dsp.text("CURR: {} mA".format(mamp), 0, 50)
        dsp.show()
        
    #send payload
    lora.println(payload)


print("WAKE UP INA")
ina.wake()


for i in range(RETRIES):
    print("PREPARING TIME SLOT NUMBER {}".format(i))
    delay = randint(1, MAXDELAY)
    sleep_ms(delay)
    print("STARTING AFTER {} ms".format(delay))
    lora_burst()


if OLED_ON:
    sleep_ms(5000) # keep results on OLED for n millisecs
    dsp.fill(0)
    dsp.show()

# POWER OFF moisture sensors before going to sleep (it will save about 10mA per sensor (20mA))
print("POWERING OFF SENSORS")
pwr_pin_S1.value(False)
pwr_pin_S2.value(False)
sleep_ms(100) 
print("ENTERING DEEP SLEEP MODE [{}-msec]...".format(deep_sleep_time_msec))
sleep_ms(100)
deepsleep(deep_sleep_time_msec)
