#from apiclient.discovery import build
from googleapiclient.discovery import build
import json
import pandas as pd
import datetime
import streamlit as st
from datetime import datetime, timedelta, timezone
from isodate import parse_duration
from dateutil import parser
import base64

with open("secret.json") as f:
    secret = json.load(f)

# API情報
API_KEY = secret["KEY"]
API_NAME = "youtube"
API_VER = "v3"

# 認証情報
youtube = build(API_NAME, API_VER,developerKey = API_KEY)

# ------------------------------------------------
def video_search(youtube, q="ポケモン",max_results = 50):
    response = youtube.search().list(
        part = "id,snippet",
        q = q,
        maxResults = max_results,
        order = "viewCount", #再生回数順
        type = "video" #動画のみ（オススメ等は含めない）
    ).execute()

    items_id = []
    items = response["items"]

    for item in items:
        item_id = {}

        item_id["動画ID"] = item["id"]["videoId"]
        item_id["チャンネル名"] = item["snippet"]["channelTitle"]
        item_id["チャンネルID"] = item["snippet"]["channelId"]
        items_id.append(item_id)

    df_video = pd.DataFrame(items_id)
    
    return df_video

# ------------------------------------------------
def get_results(def_video, threshold=0):
    channel_ids = def_video["チャンネルID"].unique().tolist()
    
    subsc_list = youtube.channels().list(
        id = ",".join(channel_ids),
        part = "snippet,statistics", 
        fields = "items(id,snippet(publishedAt),statistics(subscriberCount))" #登録者と開設日が必要なので、必要な項目を指定
    ).execute()
        
    subscribers = []
        
    for item in subsc_list["items"]:
        subscriber = {}
        
        if len(item["statistics"]) > 0:
            subscriber["チャンネルID"] = item["id"]
            subscriber["登録者数"] = int(item["statistics"]["subscriberCount"])
        else:
            subscriber["チャンネルID"] = item["id"]
        
        jst_time = parser.parse(item["snippet"]["publishedAt"])
        jst_tz = timezone(timedelta(hours=+9))
        subscriber["開設日"] = datetime.fromtimestamp(jst_time.timestamp(), jst_tz).strftime("%Y-%m-%d %H:%M")
        
        subscribers.append(subscriber)
                
    df_subscs = pd.DataFrame(subscribers)
    df = pd.merge(left=def_video, right=df_subscs, on="チャンネルID")
    df_extracted = df[df["登録者数"] >= threshold]

    video_ids = df_extracted["動画ID"].tolist()
            
    # API（videos）---------------------
    videos_list = youtube.videos().list(
    id=",".join(video_ids),
    part=["statistics", "snippet", "status", "contentDetails"],
    fields="items(id,snippet(title,publishedAt,categoryId,channelId),statistics(viewCount,likeCount,commentCount),status(privacyStatus),player(embedHtml),contentDetails(duration))"
    ).execute()
            
            
    videos_info = []

    items = videos_list["items"]
        
    for item in items:
        video_info = {}
        video_info["タイトル"] = item["snippet"]["title"]
                
        jst_time = parser.parse(item["snippet"]["publishedAt"])
        jst_tz = timezone(timedelta(hours=+9))
        video_info["投稿日"] = datetime.fromtimestamp(jst_time.timestamp(), jst_tz).strftime("%Y-%m-%d %H:%M")
                
        duration = parse_duration(item["contentDetails"]["duration"])
        video_info["時間"] = f"{duration.seconds // 3600:02}:{(duration.seconds // 60) % 60:02}:{duration.seconds % 60:02}"
                
        video_info["再生数"] = int(item.get("statistics", {}).get("viewCount", 0))
                
        like_count = item.get("statistics", {}).get("likeCount", None)
        video_info["高評価"] = "-" if like_count is None or like_count == "0" else int(like_count)
                
        comment_count = item.get("statistics", {}).get("commentCount", None)
        video_info["コメント"] = "-" if comment_count is None or comment_count == "0" else int(comment_count)          
        video_info["動画ID"] = item["id"]
        video_info["URL"] = "https://www.youtube.com/watch?v=" + item["id"]
                
        videos_info.append(video_info)
                
    df_videos_info = pd.DataFrame(videos_info)
            
    results = pd.merge(left=df_videos_info, right=df_extracted, on="動画ID")
            
    results = results.loc[:,["投稿日", "タイトル", "時間", "再生数", "高評価", "コメント","チャンネル名", "登録者数", "開設日", "URL",]]
            
    return results


#------------------------------------

st.title("YouTube分析アプリ")


st.sidebar.write("## SEARCH")
query = st.sidebar.text_input("キーワード", "風俗")


#------------------------------------
st.markdown(f"""
キーワード：{query}
""")
#- 登録者数：{theshold}

df_video = video_search(youtube, q=query, max_results = 50)
results = get_results(df_video)


st.dataframe(results,1000,1300)

csv = results.to_csv(index=False)

# utf-8(BOM)
b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
href = f'<a href="data:application/octet-stream;base64,{b64}" download="result_utf-8-sig.csv">ダウンロード</a>'
st.markdown(f"CSV（utf-8 BOM）:  {href}", unsafe_allow_html=True)


# git init
# git remote add origin https://github.com/Puiming1/Youtube_Search.git

# requirements.txt
# git add .