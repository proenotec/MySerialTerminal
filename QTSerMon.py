#!/usr/bin/python3
import threading
from Ui_interfaz import *
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit, QFileDialog
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QObject
import serial
import sys
import glob
import queue
import time

Debug = False
bufferTexto=""

def list_serial_ports():
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')
    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    if Debug: print("result",result)
    return result

def ByteToHex( byteStr ):
    return ''.join( [ "%02X " % x for x in byteStr ] ).strip()

class PerpetualTimer:
    """A Timer class that does not stop, unless you want it to."""
    def __init__(self, seconds, target, params = None):
        self._should_continue = False
        self.is_running = False
        self.seconds = seconds
        self.target = target
        self.params = params
        self.thread = None

    def _handle_target(self):
        self.is_running = True
        #self.target(self,*self.params)
        self.target(self)
        self.is_running = False
        self._start_timer()

    def _start_timer(self):
        # Code could have been running when cancel was called.
        if self._should_continue:
            self.thread = threading.Timer(self.seconds, self._handle_target)
            self.thread.start()

    def start(self):
        if not self._should_continue and not self.is_running:
            self._should_continue = True
            self._start_timer()

    def cancel(self):
        if self.thread is not None:
            # Just in case thread is running and cancel fails.
            self._should_continue = False
            self.thread.cancel()

class SerieMonitor(QObject):
    global bufferTexto
    image_signal = QtCore.pyqtSignal(str)
    @QtCore.pyqtSlot()
    def monitor_images(self):
        global bufferTexto
        contador = 1
        # I'm guessing this is an infinite while loop that monitors files
        while True:
            #self.image_signal.emit('Contador = %i' % contador)
            if (len(bufferTexto)>3):
                self.image_signal.emit(bufferTexto)
                bufferTexto=""
            #contador += 1
            time.sleep(0.1)

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    global bufferTexto
    def __init__(self, *args, **kwargs):
        QtWidgets.QMainWindow.__init__(self, *args, **kwargs)
        self.setupUi(self)

        self.ElFicheroOrigen = None
        self.ElPuertoSerieA = None
        self.ElPuertoSerieB = None
        self.Temporizador = None
        #self.bufferTexto = ""
        self.cola = queue.Queue()

        # TESTING
        self.serie_monitorA = SerieMonitor()
        self.thread = QtCore.QThread(self)
        self.serie_monitorA.image_signal.connect(self.image_callback)
        self.serie_monitorA.moveToThread(self.thread)
        self.thread.started.connect(self.serie_monitorA.monitor_images)
        self.thread.start()
        # END TESTING

        # instrucciones al inicio.
        #self.comboBox.addItems(list_serial_ports())

        # Conectando eventos con funciones
        self.actionAbrir_captura.triggered.connect(self.openFileNameDialog)
        self.pushButton_2.clicked.connect(self.hdlInicioFin)
        self.pushButton_3.clicked.connect(self.borrar)
        self.actionGuardar_captura.triggered.connect(self.saveFileNameDialog)
        #self.actionSubMenu1.triggered.connect(self.borrar)

    # TESTING
    @QtCore.pyqtSlot(str)
    def image_callback(self, mensaje):
        if Debug: print(mensaje)
        #mensaje = mensaje
        #self.plainTextEdit.appendPlainText(mensaje)
        self.plainTextEdit.insertPlainText(mensaje)
        self.plainTextEdit.moveCursor(QtGui.QTextCursor.End)
    # END TESTING

    # Funciones para los eventos
    def borrar(self):
        self.plainTextEdit.clear()

    def openFileNameDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","All Files (*);;Python Files (*.py)", options=options)
        if fileName:
            if Debug: print(fileName)
            #self.textEdit.setText(fileName)
            #self.textEdit.moveCursor(QtGui.QTextCursor.End)
            #Se abre el archivo y se muestra el contenido en el QTextEdit
            fname = open(fileName)
            data = fname.read()
            self.textEdit.setText(data)

    def saveFileNameDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getSaveFileName(self,"QFileDialog.getOpenFileName()", "","All Files (*);;Python Files (*.py)", options=options)
        if fileName:
            if Debug: print(fileName)
            #self.textEdit.setText(fileName)
            #self.textEdit.moveCursor(QtGui.QTextCursor.End)
            #Se abre el archivo y se muestra el contenido en el QTextEdit
            fname = open(fileName,"w")
            data = self.textEdit.toPlainText()
            fname.write(data)
            fname.close()



    def hdlInicioFin(self):
        if Debug: print("hdlInicioFin", self.pushButton_2.text())
        if (self.pushButton_2.text() == "Iniciar"):
            self.pushButton_2.setText("Parar")
            if Debug: print("Activar función")
            # Cálculo del retardo entre bytes en segundos
            try:
                retardo = int(self.textEdit_2.toPlainText())
                if Debug: print("retardo =", retardo)
            except Exception as e:
                if Debug: print ("Error: Fallo al leer valor de retardo: " + str(e))
                retardo = 0
            if (retardo > 0):
                retardo = retardo / 1000000
            else:
                retardo = 0.1
            # Apertura del fichero en modo binario
            try:
                MiFichero = self.textEdit.toPlainText()
                self.ElFicheroOrigen = open(MiFichero,"r+b")
            except Exception as e:
                if Debug: print ("Error: Abriendo el fichero de datos: " + str(e))
                self.pushButton_2.setText("Iniciar")
                return
            # Apertura del puerto serie.
            MiPuertoSerie = self.comboBox.currentText()
            MisBaudios = 9600
            try:
                self.ElPuertoSerieA = serial.Serial(MiPuertoSerie, MisBaudios)
                self.ElPuertoSerieA.bytesize = serial.EIGHTBITS #number of bits per bytes
                self.ElPuertoSerieA.parity = serial.PARITY_NONE #set parity check: no parity
                self.ElPuertoSerieA.stopbits = serial.STOPBITS_ONE #number of stop bits
                self.ElPuertoSerieA.timeout = None          #block read
                self.ElPuertoSerieA.xonxoff = False     #disable software flow control
                self.ElPuertoSerieA.rtscts = False     #disable hardware (RTS/CTS) flow control
                self.ElPuertoSerieA.dsrdtr = False       #disable hardware (DSR/DTR) flow control
                self.ElPuertoSerieA.writeTimeout = 0     #timeout for write
                #ser.open()
            except Exception as e:
                if Debug: print ("Error: Abriendo el puerto serie: " + str(e))
                self.pushButton_2.setText("Iniciar")
                return          
            self.Temporizador = PerpetualTimer(retardo, self.EnvioTemporizado)
            self.Temporizador.start()
            self.TemporizadorDisplay = PerpetualTimer(0.250,self.TemporizadorActivaDisplay)
            self.TemporizadorDisplay.start()
        else:
            if Debug: print("Desactivar función")
            self.pushButton_2.setText("Iniciar")
            try:
                self.Temporizador.cancel()
                del(self.Temporizador)
                self.TemporizadorDisplay.cancel()
                del(self.TemporizadorDisplay)
            except:
                if Debug: print("")

    def EnvioTemporizado(self, Otro):
        global bufferTexto
        try:
            UltimoByte = self.ElFicheroOrigen.read(1)
        except Exception as e:
            if Debug: print ("Error: Leyendo el fichero de datos: " + str(e))
        if not(UltimoByte):
            if Debug: print("FIN")
            if self.checkBox.isChecked():
                self.ElFicheroOrigen.seek(0, 0)
            else:
                self.Temporizador.cancel()
                del(self.Temporizador)
                self.pushButton_2.setText("Iniciar")
                self.TemporizadorDisplay.cancel()
                del(self.TemporizadorDisplay)
        else:
            if Debug: print("Escribiendo en el puerto serie: 0x%s" % ByteToHex(UltimoByte))
            if self.ElPuertoSerieA.isOpen():
                self.ElPuertoSerieA.write(bytearray(UltimoByte))
                #self.bufferTexto = "0x" + ByteToHex(UltimoByte) + "\n" + self.bufferTexto
                bufferTexto = bufferTexto + "0x" + ByteToHex(UltimoByte)+" "
if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()