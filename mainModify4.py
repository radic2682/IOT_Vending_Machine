import time
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

import RPi.GPIO as GPIO
import RPi_I2C_driver as I2C

########## Firebase Setting ##########
cred = credentials.Certificate("/home/pi/Project/rasberry-596de-firebase-adminsdk-sm1ch-a946597156.json")
firebase_admin.initialize_app(cred,{
    'databaseURL' : 'https://rasberry-596de-default-rtdb.firebaseio.com/'
})
ref = db.reference() #기본 위치 지정
######################################

# Define Pins
motor360_pin        = 13    # product output motor
motor180_pin        = 18    # purchase/retrun select motor
siren_pin           = 22    # purchase/retrun select motor
purchase_btn_pin    = 23    # purchase button
return_btn_pin      = 24    # retrun button
call_btn_pin        = 26    # menager call button
sensor500_pin       = 21    # count 500won
sensor100_pin       = 20    # count 100won
sensorStopMotor_pin = 25    # Sensor to stop 360 degree motor
red_LED_pin         = 27    # red LED
green_LED_pin       = 17    # green LED

# GPIO Pin Setting
GPIO.setmode(GPIO.BCM)

GPIO.setup(motor360_pin, GPIO.OUT)
GPIO.setup(motor180_pin, GPIO.OUT)
GPIO.setup(siren_pin, GPIO.OUT)
GPIO.setup(purchase_btn_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(return_btn_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(call_btn_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(sensor500_pin, GPIO.IN)
GPIO.setup(sensor100_pin, GPIO.IN)
GPIO.setup(sensorStopMotor_pin, GPIO.IN)
GPIO.setup(red_LED_pin, GPIO.OUT)
GPIO.setup(green_LED_pin, GPIO.OUT)

# Motor Setting
motor180LeftDutyCycle = 11.5
motor180MiddleDutyCycle = 9.0
motor180RightDutyCycle = 7.0

pwm360 = GPIO.PWM(motor360_pin, 50)  # 50Hz (서보모터 PWM 동작을 위한 주파수)
pwm360.start(0) #서보의 정지 상태
pwm180 = GPIO.PWM(motor180_pin, 50)  # 50Hz (서보모터 PWM 동작을 위한 주파수)
pwm180.start(motor180MiddleDutyCycle) #서보의 0도 위치


# 180도 모터를 가운데로 설정
pwm180.ChangeDutyCycle(motor180MiddleDutyCycle)
time.sleep(1.0)

# Class & Function Define
class VendingMachine:
    def __init__(self, count_500, count_100, count_earn, count_stock, product_output_ongoing):
        self.count_500 = count_500
        self.count_100 = count_100
        self.count_earn = count_earn
        self.count_stock = count_stock
        self.product_output_ongoing = product_output_ongoing
        
    def Reset(self):
        self.count_500 = 0
        self.count_100 = 0

    def Calculate(self):
        return self.count_500 * 500 + self.count_100 * 100

    def DisplaySetting(self):
        mylcd.lcd_display_string(f"Total: {self.Calculate()}     ",2)

    def Add(self, coin):
        if coin == 500:
            self.count_500 += 1
        else:
            self.count_100 += 1

    def AccumulateCoin(self):
        self.count_earn += 700

    def ReduceStock(self):
        self.count_stock -= 1

    def updateFromDatabase(self):
        try:
            self.count_stock = int(db.reference('vendingM/stock').get())
            self.count_earn = int(db.reference('vendingM/earnCoin').get())
            print(f'firestore로부터 데이터를 받아옵니다.')
            print(f'현재 재고: {self.count_stock}개')
            print(f'현재 수입: {self.count_earn}원')

        except:
            print(u'No such document!')

def buttonPushed(sentence, m_control1):
    mylcd.lcd_display_string(f"{sentence}",2)
    pwm180.ChangeDutyCycle(m_control1)
    time.sleep(1.3)
    pwm180.ChangeDutyCycle(motor180MiddleDutyCycle)
    time.sleep(1.0)

def initDisplay():
    mylcd.lcd_display_string("Welcome Vend.M  ",1)
    mylcd.lcd_display_string("Insert a coin   ",2)

# Create Coin & Initialization
vendingMachine = VendingMachine(0, 0, 0, 0, False)
vendingMachine.updateFromDatabase()


# 디스플레이 개체 생성 & 초기 설정
mylcd = I2C.lcd()
initDisplay()

# Interrupt
def callback_By_500(channel):
    print("500원이 들어옴")
    vendingMachine.Add(500)
    vendingMachine.DisplaySetting()

def callback_By_100(channel):
    print("100원이 들어옴")
    vendingMachine.Add(100)
    vendingMachine.DisplaySetting()

def callback_By_return_btn_pin(channel):
    print("retrun button 눌림")
    vendingMachine.Reset()
    buttonPushed(f"Return Complete", motor180RightDutyCycle)
    initDisplay()

def callback_By_purchase_btn_pin(channel):
    print("purchase button 눌림")
    
    if vendingMachine.count_stock != 0:
        if vendingMachine.Calculate() == 700:
            print("700원 충족 - 구매됨")
            GPIO.output(green_LED_pin, 1)
            buttonPushed(f"Purchase Success", motor180LeftDutyCycle)
            vendingMachine.AccumulateCoin()
            vendingMachine.ReduceStock()
            vendingMachine.Reset()

            db.reference('vendingM').update({'earnCoin':vendingMachine.count_earn})
            db.reference('vendingM').update({'stock':vendingMachine.count_stock})
            print(f"총 수익:{vendingMachine.count_earn} - firebase에 업로드 완료")
            print(f"남은 재고:{vendingMachine.count_stock} - firebase에 업로드 완료")
            
            vendingMachine.product_output_ongoing = True
            # product out
            pwm360.ChangeDutyCycle(1.5)
            # 이 뒤로는 sensorStopMotor의 Interrupt로 처리

        elif vendingMachine.Calculate() < 700:
            print("700원 충족되지 못함 - 구매 불가")

            mylcd.lcd_display_string(f"Can't purchase  ",1)
            mylcd.lcd_display_string(f"Not Enough coin",2)
            time.sleep(1.5)
            initDisplay()
            vendingMachine.DisplaySetting()

        elif vendingMachine.Calculate() > 700:
            print("700원 충족되지 못함 - 구매 불가")

            mylcd.lcd_display_string(f"Can't purchase  ",1)
            buttonPushed(f"Too many coins", motor180RightDutyCycle)
            vendingMachine.Reset()
            time.sleep(1.5)

            initDisplay()
    else:
        print("재고가 없음 -  구매 불가")
        mylcd.lcd_display_string(f"Can't purchase  ",1)
        buttonPushed(f"Out of stock    ", motor180RightDutyCycle)
        time.sleep(1.5)
        vendingMachine.Reset()
        initDisplay()

def callback_By_call_btn_pin(channel):
    db.reference('vendingM').update({'Message':"자판기의 사용자에게 문제가 발생하였습니다."})
    print("call button 눌림 - 관리자에게 알림")
    mylcd.lcd_display_string(f"Call Success!   ",1)
    mylcd.lcd_display_string(f"Wait a minute.  ",2)
    time.sleep(1.5)
    initDisplay()
    

def callback_By_sensorStopMotorandWarning_pin(channel):
    if vendingMachine.product_output_ongoing == True:
        print("과자가 나옴")
        pwm360.start(0) #서보의 정지 상태
        GPIO.output(green_LED_pin, 0)
        initDisplay()
        time.sleep(8.0)
        vendingMachine.product_output_ongoing = False

    else:
        GPIO.output(siren_pin, 1)
        GPIO.output(red_LED_pin, 1)
        time.sleep(1.0)
        GPIO.output(siren_pin, 0)
        GPIO.output(red_LED_pin, 0)

        db.reference('vendingM').update({'Message':"자판기의 도난이 의심됨"})
        print(f"자판기의 도난이 의심됨 - 관리자에게 알림")

GPIO.add_event_detect(sensor100_pin, GPIO.FALLING, callback=callback_By_100, bouncetime=250)
GPIO.add_event_detect(sensor500_pin, GPIO.FALLING, callback=callback_By_500, bouncetime=250)
GPIO.add_event_detect(return_btn_pin, GPIO.FALLING, callback=callback_By_return_btn_pin, bouncetime=5000)
GPIO.add_event_detect(purchase_btn_pin, GPIO.FALLING, callback=callback_By_purchase_btn_pin, bouncetime=5000)
GPIO.add_event_detect(call_btn_pin, GPIO.FALLING, callback=callback_By_call_btn_pin, bouncetime=5000)
GPIO.add_event_detect(sensorStopMotor_pin, GPIO.FALLING, callback=callback_By_sensorStopMotorandWarning_pin, bouncetime=10000)


# Polling Function (Main)
try:
    while True:
        print("대기중")
        time.sleep(2)

        if int(db.reference('vendingM/RaspUpdateSignal').get()) == 1:
            vendingMachine.updateFromDatabase()
            db.reference('vendingM').update({'Message':"자판기 정보 업데이트 완료"})
            db.reference('vendingM').update({'RaspUpdateSignal':0})

# 프로그램 종료, (Ctrl + C를 입력)
except KeyboardInterrupt:
    print('프로그램을 종료합니다.')

finally:
    pwm360.stop()
    pwm180.stop()
    GPIO.cleanup()
