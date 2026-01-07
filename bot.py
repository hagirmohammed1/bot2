# بوت خفيف لا يحتاج ffmpeg أو pydub
# يعتمد فقط على Vosk أو SpeechRecognition
# يدعم التسجيلات الطويلة، العربية والإنجليزية، ويقسم النص على عدة رسائل

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import os
import math
import time

TOKEN = os.environ.get("TOKEN", "8584666863:AAHZ3xApgMsvioTzkd7BoIed38z5VKCSYaE")
MAX_MESSAGE_LENGTH = 3500
CHUNK_LENGTH_MS = 60_000

# التحقق من المكتبات المتوفرة
USE_VOSK = False
USE_SPEECHREC = False
try:
    from vosk import Model, KaldiRecognizer
    USE_VOSK = True
except:
    import speech_recognition as sr
    USE_SPEECHREC = True

# تحميل نموذج Vosk إذا متوفر
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

    full_text = ""

    # تقسيم الصوت باستخدام Wave (بدون pydub)
    import wave
    with wave.open(input_path, 'rb') as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        duration_ms = (frames / rate) * 1000
        chunks = math.ceil(duration_ms / CHUNK_LENGTH_MS)

        progress_message = await message.reply_text(
            f"⏳ بدء المعالجة...\n🔄 التقدم: 0% (0 / {chunks})\n⏱️ الوقت المتبقي: --"
        )

        for i in range(chunks):
            start_frame = int(i * CHUNK_LENGTH_MS * rate / 1000)
            end_frame = int(min((i + 1) * CHUNK_LENGTH_MS * rate / 1000, frames))
            wf.setpos(start_frame)
            data = wf.readframes(end_frame - start_frame)

            text = ""
            if USE_VOSK:
                import json
                rec = KaldiRecognizer(vosk_model, rate)
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get('text','')
            elif USE_SPEECHREC:
                r = sr.Recognizer()
                from io import BytesIO
                audio_file = sr.AudioFile(BytesIO(data))
                with audio_file as source:
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

            # تحديث نسبة التقدم
            elapsed = time.time() - update.message.date.timestamp()
            completed = i + 1
            avg_time_per_chunk = elapsed / completed if completed else 0
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

    print("🎉 Lightweight Speech to Text Bot is running!")
    app.run_polling()
