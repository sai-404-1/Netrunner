from computer.module.base_module import CommandModule


class UserModule(CommandModule):
    slug = "sound_pinger"
    command = (
        "cat << 'PYEOF' > /tmp/sp.py\n"
        "import wave,math,struct,subprocess,os,sys\n"
        "sr=44100;f=float(sys.argv[1]);d=float(sys.argv[2]);v=float(sys.argv[3])\n"
        "n=int(sr*d);buf=wave.open('/tmp/sp.wav','wb')\n"
        "buf.setnchannels(1);buf.setsampwidth(2);buf.setframerate(sr)\n"
        "for i in range(n):\n"
        "  t=i/sr;val=int(math.sin(2*math.pi*f*t)*32767*v)\n"
        "  buf.writeframes(struct.pack('<h',max(-32768,min(32767,val))))\n"
        "buf.close()\n"
        "subprocess.run(['amixer','set','Master','50%'],capture_output=True)\n"
        "subprocess.run(['/usr/bin/ffmpeg','-i','/tmp/sp.wav','-f','alsa','default','-loglevel','quiet'],capture_output=True)\n"
        "os.remove('/tmp/sp.wav')\n"
        "print(f'Sound played: {f}Hz {d}s vol={v}')\n"
        "PYEOF\n"
        "python3 /tmp/sp.py $freq $duration $volume"
    )

    def __init__(self):
        self.title = "Звуковой пингер"
        self.description = "Воспроизводит звуковой сигнал заданной частоты и длительности на удалённом хосте через ffmpeg."

    schema = {
        "placeholders": [
            ["freq",     "Частота (Гц)",       "440",                "select",
             [["220", "220 Гц (низкий)"], ["440", "440 Гц (стандарт)"],
              ["660", "660 Гц"], ["880", "880 Гц (высокий)"],
              ["1000", "1 кГц"], ["2000", "2 кГц"],
              ["55", "55 Гц (суббас)"], ["120", "120 Гц (бас)"]]],
            ["duration", "Длительность (сек)", "0.5",               "select",
             [["0.1", "0.1 с (щелчок)"], ["0.3", "0.3 с (короткий)"],
              ["0.5", "0.5 с"], ["1.0", "1 с"], ["2.0", "2 с"],
              ["5.0", "5 с"], ["10.0", "10 с"]]],
            ["volume",   "Громкость (%)",       "50",                "select",
             [["10", "10%"], ["25", "25%"], ["50", "50%"],
              ["75", "75%"], ["100", "100%"]]],
        ]
    }
