from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from google import genai

app = Flask(__name__)

# =====================================================
# ★ 請在下方三個地方貼上你的金鑰 ★
# =====================================================

LINE_CHANNEL_SECRET = '76c6cef43f5824e4db29fee910099329'          # ← 貼在這裡
LINE_CHANNEL_ACCESS_TOKEN = 'cmfkifhR7yxF9FuwSDOZu9e0oXCMYrw0I4aq3U2SVXEPgJDZTK6sJgn0wYfJjt4Yve97J+V/wc0o++hn/RtUxUDpP4VgpNsXyUdXfNpKIEE1p2Tn9nLjbjVtgiHNS7PmfVYmDgt37zbZ1k2lPCT0NQdB04t89/1O/w1cDnyilFU='   # ← 貼在這裡
GEMINI_API_KEY = 'AIzaSyDx-mQt23CCL9kvOxhhLHyGq2kSg8jRW-8'           # ← 這裡


# =====================================================

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

client = genai.Client(api_key=GEMINI_API_KEY)


@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=user_msg
        )
        reply = response.text
    except Exception as e:
        reply = '抱歉，我現在有點忙，請稍後再試！'

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )


if __name__ == "__main__":
    app.run()
