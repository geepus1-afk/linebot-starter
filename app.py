import os
import json
import datetime
import traceback
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from google.api_core.client_options import ClientOptions

app = Flask(__name__)

# 從 Render 環境變數中安全讀取金鑰與設定
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
GOOGLE_CREDENTIALS = os.environ.get('GOOGLE_CREDENTIALS')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 設定 Google Gemini API 金鑰
genai.configure(api_key=GEMINI_API_KEY)

# 💡 量身打造：設定 AI 教學助理的「筆記整理大師」Prompt 霊魂
SYSTEM_PROMPT = """
你是一位專業的大學教學助理，專長是引導學生將凌亂的課堂筆記轉化為系統化的知識。
當學生傳送課堂筆記、錄音逐字稿或課文片段給你時，你必須嚴格遵循以下「引導式教學步驟」回覆：

1. 🎯 【友善鼓勵】：先用親切的語氣稱讚學生願意動手整理筆記。
2. 📝 【結構化整理】：將學生傳來的凌亂文字，重新整理成包含「核心觀念說明」與「重點條列」的清晰筆記。
3. 🔍 【關鍵字科普】：挑出筆記中 1~2 個最重要的專有名詞，提供淺顯易懂的解釋。
4. ❓ 【教學引導互動（核心！）】：這一步嚴禁給出結論。請根據這份筆記的內容，設計「一個概念小測驗問題」，並溫柔地對學生說：「以上是幫你整理的重點！為了確認你有完全理解，助教想考考你：『[填入你的問題]』？歡迎直接回覆我你的答案，助教幫你批改喔！」

請全程使用繁體中文（台灣）回答，語氣必須充滿耐心、多使用鼓勵的表情符號（如 😊、✨、📝）。
"""

# 呼叫新版 Gemini 模型並注入 System Instruction
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction=SYSTEM_PROMPT
)

def get_sheets_service():
    try:
        creds_info = json.loads(GOOGLE_CREDENTIALS)
        creds = Credentials.from_service_account_info(
            creds_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        # 修正新版 Google API 在某些伺服器上的認證連線問題
        from googleapiclient.discovery import build
        service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
        return service
    except Exception as e:
        print(f'Sheets 憑證載入或連線錯誤: {e}')
        traceback.print_exc()
        return None

def log_to_sheets(user_msg, bot_reply):
    service = get_sheets_service()
    if service is None:
        print("無法取得 Sheets 服務，取消紀錄")
        return
    try:
        now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
        values = [[now, user_msg, bot_reply]]
        body = {'values': values}
        
        # 寫入指定的試算表與「工作表1」分頁
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range='工作表1!A:C',
            valueInputOption='USER_ENTERRED',
            body=body
        ).execute()
        print("對話紀錄成功自動寫入試算表！")
    except Exception as e:
        print(f'試算表寫入失敗: {e}')
        traceback.print_exc()

@app.route("/webhook", formats=["POST"])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    try:
        # 讓 Gemini 根據筆記大腦生成回應
        response = model.generate_content(user_message)
        reply_text = response.text
    except Exception as e:
        print(f"Gemini 生成失敗: {e}")
        reply_text = "抱歉，助教的大腦開小差了，請再傳一次筆記給試試看！"

    # 將紀錄同步進 Google 試算表
    log_to_sheets(user_message, reply_text)
    
    # 回傳給 LINE 使用者
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run()
