# بوت تحويل الصوت إلى نص يعتمد على أفضل مكتبة متوفرة
# يدعم التسجيلات الطويلة، العربية والإنجليزية، وعرض التقدم والوقت المتبقي
# يختار تلقائيًا بين Whisper, Vosk, أو Google SpeechRecognition

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from pydub import AudioSegment
import os
import math
import time

# التوكن
TOKEN = os.environ.get("TOKEN", "8584666863:AAHZ3xApgMsvioTzkd7BoIed38z5VKCSYaE")

MAX_MESSAGE_LENGTH = 3500
CHUNK_LENGTH_MS = 60_000

# محاولة استيراد المكتبات بالترتيب
USE_WHISPER = False
USE_VOSK = False
USE_SPEECHREC = False

try:
    import whisper
    USE_WHISPER = True
except:
    try:
        from vosk import Model, KaldiRecognizer
        USE_VOSK = True
    except:
        try:
            import speech_recognition as sr
            USE_SPEECHREC = True
        except:
            pass

# تحميل نموذج Whisper إذا كان متاحًا
if USE_WHISPER:
    model = whisper.load_model("small")

# تحميل نموذج Vosk إذا كان متاحًا
if USE_VOSK:
    if not os.path.exists("vosk-model"):
        print("⚠️ لا يوجد نموذج Vosk، يجب تحميله يدويًا")
    else:
        vosk_model = Model("vosk-model")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙️ مرحبًا! أرسل رسالة صوتية لأحولها إلى نص")

async def send_long_text(message, text):
    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        await message.reply_text(text[i:i + MAX_MESSAGE_LENGTH])

async def speech_to_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not (message.voice or message.audio):
        await message.reply_text("⚠️ أرسل رسالة صوتية أو ملف صوتي فقط")
        return

    file = await (message.voice.get_file() if message.voice else message.audio.get_file())
    input_path = "input_audio"
    wav_path = "full_audio.wav"
    await file.download_to_drive(input_path)

    # تحويل الصوت إلى WAV
    sound = AudioSegment.from_file(input_path)
    sound = sound.set_channels(1).set_frame_rate(16000)
    sound.export(wav_path, format="wav")

    full_text = ""
    chunks = math.ceil(len(sound) / CHUNK_LENGTH_MS)
    start_time = time.time()

    progress_message = await message.reply_text(
        f"⏳ بدء المعالجة...\n🔄 التقدم: 0% (0 / {chunks})\n⏱️ الوقت المتبقي: --"
    )

    for i in range(chunks):
        start_ms = i * CHUNK_LENGTH_MS
        end_ms = min((i + 1) * CHUNK_LENGTH_MS, len(sound))
        chunk = sound[start_ms:end_ms]

        chunk_path = f"chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")

        text = ""
        # استخدام أفضل مكتبة متوفرة
        if USE_WHISPER:
            result = model.transcribe(chunk_path, language="auto", fp16=False)
            text = result['text'].strip()
        elif USE_VOSK:
            import wave, json
            wf = wave.open(chunk_path, "rb")
            rec = KaldiRecognizer(vosk_model, wf.getframerate())
            data = wf.readframes(wf.getnframes())
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                text = res.get('text','')
            wf.close()
        elif USE_SPEECHREC:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(chunk_path) as source:
                audio_data = r.record(source)
                try:
                    text = r.recognize_google(audio_data, language="ar-AR")
                except:
                    try:
                        text = r.recognize_google(audio_data, language="en-US")
                    except:
                        text = ""

        if text:
            full_text += text + "\n"

        os.remove(chunk_path)

        elapsed = time.time() - start_time
        completed = i + 1
        avg_time_per_chunk = elapsed / completed
        remaining_chunks = chunks - completed
        remaining_seconds = int(avg_time_per_chunk * remaining_chunks)
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        percent = int((completed / chunks) * 100)

        await progress_message.edit_text(
            f"⏳ جارٍ معالجة الصوت...\n"
            f"🔄 التقدم: {percent}% ({completed} / {chunks})\n"
            f"⏱️ الوقت المتبقي: {minutes} دقيقة {seconds} ثانية"
        )

    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(wav_path): os.remove(wav_path)

    if not full_text.strip():
        await progress_message.edit_text("⚠️ لم أتمكن من استخراج نص واضح من الصوت")
        return

    await progress_message.edit_text("✅ اكتملت المعالجة بنسبة 100%")
    header = "📝 النص المستخرج من التسجيل الصوتي:\n\n"
    await send_long_text(message, header + full_text.strip())

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, speech_to_text))

    print("🎉 Adaptive Speech to Text Bot is running!")
    app.run_polling()
