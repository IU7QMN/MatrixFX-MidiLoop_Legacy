//// ARDUINO NANO /////
//#include <EEPROM.h>
char receivedChar;
boolean newData = false;
int stayon = 300;
int stayoff = 100;

void setup() {
    pinMode(13, OUTPUT);
    digitalWrite(13, LOW);
    pinMode(2, OUTPUT);
    digitalWrite(2, LOW);
    pinMode(3, OUTPUT);
    digitalWrite(3, LOW);
    pinMode(4, OUTPUT);
    digitalWrite(4, LOW);
    pinMode(5, OUTPUT);
    digitalWrite(5, LOW);
    pinMode(6, OUTPUT);
    digitalWrite(6, LOW);
    pinMode(7, OUTPUT);
    digitalWrite(7, LOW);
    pinMode(8, OUTPUT);
    digitalWrite(8, LOW);
    pinMode(9, OUTPUT);
    digitalWrite(9, LOW);
    pinMode(10, OUTPUT);
    digitalWrite(10, LOW);
    pinMode(11, OUTPUT);
    digitalWrite(11, LOW);
    pinMode(12, OUTPUT);
    digitalWrite(12, LOW);
    pinMode(14, OUTPUT);
    digitalWrite(14, LOW);
    pinMode(15, OUTPUT);
    digitalWrite(15, LOW);
    pinMode(16, OUTPUT);
    digitalWrite(16, LOW);
    pinMode(17, OUTPUT);
    digitalWrite(17, LOW);
    pinMode(18, OUTPUT);
    digitalWrite(18, LOW);
// CLOSE A6 AND A7 TO GND
  //  stayon = EEPROM.read(2);
  //  stayoff = EEPROM.read(4);
    Serial.begin(115200);
    Serial.println(F("MatrixFX v.19.0626.A by IU7QMN"));
    Serial.println(F("Enable first..."));
    delay(2000);
    Serial.println(F("<MatrixFX is ready>"));
}

void loop() {
    recvOneChar();
    showNewData();
    
}

void recvOneChar() {
    if (Serial.available() > 0) {
        receivedChar = Serial.read();
        newData = true;
    }
}

void showNewData() {
    if (newData == true) {
      switch (receivedChar){
      case '1':
        Serial.print(receivedChar);
        digitalWrite(2, HIGH);
        delay(stayon);
        digitalWrite(2, LOW);
        delay(stayoff);
        break;
      case '2':
        Serial.print(receivedChar);
        digitalWrite(3, HIGH);
        delay(stayon);
        digitalWrite(3, LOW);
        delay(stayoff);
        break;
      case '3':
        Serial.print(receivedChar);
        digitalWrite(4, HIGH);
        delay(stayon);
        digitalWrite(4, LOW);
        delay(stayoff);
        break;
      case 'A':
        Serial.print(receivedChar);
        digitalWrite(5, HIGH);
        delay(stayon);
        digitalWrite(5, LOW);
        delay(stayoff);
        break;
      case '4':
        Serial.print(receivedChar);
        digitalWrite(6, HIGH);
        delay(stayon);
        digitalWrite(6, LOW);
        delay(stayoff);
        break;
      case '5':
        Serial.print(receivedChar);
        digitalWrite(7, HIGH);
        delay(stayon);
        digitalWrite(7, LOW);
        delay(stayoff);
        break;
      case '6':
        Serial.print(receivedChar);
        digitalWrite(8, HIGH);
        delay(stayon);
        digitalWrite(8, LOW);
        delay(stayoff);
        break;
      case 'B':
        Serial.print(receivedChar);
        digitalWrite(9, HIGH);
        delay(stayon);
        digitalWrite(9, LOW);
        delay(stayoff);
        break;
      case '7':
        Serial.print(receivedChar);
        digitalWrite(10, HIGH);
        delay(stayon);
        digitalWrite(10, LOW);
        delay(stayoff);
        break;
      case '8':
        Serial.print(receivedChar);
        digitalWrite(11, HIGH);
        delay(stayon);
        digitalWrite(11, LOW);
        delay(stayoff);
        break;
      case '9':
        Serial.print(receivedChar);
        //Serial.println();
        digitalWrite(12, HIGH);
        delay(stayon);
        digitalWrite(12, LOW);
        delay(stayoff);
        break;
      case 'C':
        Serial.print(receivedChar);
        //Serial.println();
        digitalWrite(14, HIGH);
        delay(stayon);
        digitalWrite(14, LOW);
        delay(stayoff);
        break;
      case '*':
        Serial.print(receivedChar);
        Serial.println();
        digitalWrite(15, HIGH);
        delay(stayon);
        digitalWrite(15, LOW);
        delay(stayoff);
        break;
      case '0':
        Serial.print(receivedChar);
        //Serial.println();
        digitalWrite(16, HIGH);
        delay(stayon);
        digitalWrite(16, LOW);
        delay(stayoff);
        break;
      case 'a':
        Serial.print("A");
        //Serial.println();
        digitalWrite(5, HIGH);
        delay(stayon);
        digitalWrite(5, LOW);
        delay(stayoff);
        break;
      case 'b':
        Serial.print("B");
        //Serial.println();
        digitalWrite(9, HIGH);
        delay(stayon);
        digitalWrite(9, LOW);
        delay(stayoff);
        break;
      case 'c':
        Serial.print("C");
        //Serial.println();
        digitalWrite(14, HIGH);
        delay(stayon);
        digitalWrite(14, LOW);
        delay(stayoff);
        break;
      case 'd':
        Serial.print("D");
        Serial.println();
        digitalWrite(18, HIGH);
        delay(stayon);
        digitalWrite(18, LOW);
        delay(stayoff);
        break;
      case '#':
        Serial.print(receivedChar);
        Serial.println();
        digitalWrite(17, HIGH);
        delay(stayon);
        digitalWrite(17, LOW);
        delay(stayoff);
        break;
      case 'D':
        Serial.print(receivedChar);
        Serial.println();
        digitalWrite(18, HIGH);
        delay(stayon);
        digitalWrite(18, LOW);
        delay(stayoff);
        break;
      // SPECIAL FUNCTION //
      case 'M':
        //Serial.print(receivedChar);
        Serial.println("MANUAL MODE");
        digitalWrite(2, HIGH);
        delay(5500);
        digitalWrite(2, LOW);
        delay(stayoff);
        break;
      case 'O':
        //Serial.print(receivedChar);
        Serial.println("AUTO MODE");
        digitalWrite(16, HIGH);
        delay(stayon);
        digitalWrite(16, LOW);
        delay(stayoff);
        break;
      case 'S':
        Serial.print(receivedChar);
        Serial.println("TOP");
        digitalWrite(13, LOW);
        break;
      } 
        
        newData = false;
    }
}