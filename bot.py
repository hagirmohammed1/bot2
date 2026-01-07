from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import speech_recognition as sr
from pydub import AudioSegment
import os
import math
import time

TOKEN = "8584666863:AAHZ3xApgMsvioTzkd7BoIed38z5VKCSYaE"

WELCOME_TEXT = (
    "🎙️ مرحباً بك في بوت تحويل الصوت إلى نص 🎙️\n"
    "📩 أرسل رسالة صوتية أو ملف صوتي (حتى لو كان طويلاً)، وسأحوله إلى نص عربي أو إنجليزي"
)

MAX_MESSAGE_LENGTH = 3500  # أقل من حد تيليجرام للأمان
CHUNK_LENGTH_MS = 60_000   # تقسيم الصوت إلى مقاطع (60 ثانية)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT)

async def send_long_text(message, text):
    """إرسال نص طويل على عدة رسائل"""
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

    # تحميل وتحويل الصوت
    sound = AudioSegment.from_file(input_path)
    sound = sound.set_channels(1).set_frame_rate(16000)
    sound.export(wav_path, format="wav")

    recognizer = sr.Recognizer()
    full_text = ""

    # تقسيم الصوت الطويل
    chunks = math.ceil(len(sound) / CHUNK_LENGTH_MS)

    start_time = time.time()

    progress_message = await message.reply_text(
        f"⏳ بدء المعالجة...\n🔄 التقدم: 0% (0 / {chunks})\n⏱️ الوقت المتبقي: --"
    )

    for i in range(chunks):
        chunk_start = i * CHUNK_LENGTH_MS
        chunk_end = min((i + 1) * CHUNK_LENGTH_MS, len(sound))
        chunk = sound[chunk_start:chunk_end]

        chunk_path = f"chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")

        with sr.AudioFile(chunk_path) as source:
            audio_data = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio_data, language="ar-AR")
        except:
            try:
                text = recognizer.recognize_google(audio_data, language="en-US")
            except:
                text = ""

        if text:
            full_text += text + "\n"

        os.remove(chunk_path)

        # حساب التقدم والوقت المتبقي
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

    # تنظيف الملفات
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

    print("🎉 Speech to Text Bot is running with progress & ETA...")
    app.run_polling()
