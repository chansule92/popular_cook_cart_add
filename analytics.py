import pandas as pd
from datetime import datetime, timedelta
import os
import json
from youtube_transcript_api import YouTubeTranscriptApi
def get_weekly_top_10():
    all_data = []
    today = datetime.now()
    date_list = [(today - timedelta(days=i)).strftime('%Y%m%d') for i in range(8)]
    for date in date_list:
        file_name = f"{date}video_view.csv"
        if os.path.exists(file_name):
            df = pd.read_csv(file_name)
            # 파일별로 수집된 날짜 정보를 추가 (기존 recorded_at 활용)
            all_data.append(df)
    
    if not all_data:
        print("분석할 데이터 파일이 없습니다.")
    combined_df = pd.concat(all_data, ignore_index=True)
        
    # 3. 영상별 '최초 조회수'와 '최종 조회수' 찾기
    # recorded_at 기준으로 정렬하여 첫 값과 마지막 값을 가져옵니다.
    combined_df = combined_df.sort_values(by=['video_id', 'recorded_at'])
    
    stats = combined_df.groupby('video_id').agg(
        title=('title', 'first'),
        start_view=('view_count', 'first'),
        first_date=('recorded_at', 'first')
    ).reset_index()
    summary_file_name = f"{today.strftime('%Y%m%d')}view_summary.csv"
    if os.path.exists(summary_file_name):
        summary_stats = pd.read_csv(summary_file_name)
    merge_df = pd.merge(stats,summary_stats,on='video_id',how='inner')
    
    merge_df['first_date'] = pd.to_datetime(merge_df['first_date'])
    today_dt = pd.to_datetime(today.strftime('%Y-%m-%d'))
    # 2. 날짜 차이 계산 (최소 1일로 설정하여 ZeroDivision 에러 방지)
    merge_df['days_diff'] = (today_dt - merge_df['first_date']).dt.days
    merge_df.loc[merge_df['days_diff'] < 1, 'days_diff'] = 1
    merge_df['daily_growth'] = (merge_df['current_view'] - merge_df['start_view']) / merge_df['days_diff']
    
    top_20 = merge_df.sort_values(by='daily_growth', ascending=False).head(20)
    return top_20

def material_extraction(video_id):
    transcript_list = YouTubeTranscriptApi().list(video_id)
    transcript = transcript_list.find_transcript(['ko','en'])
    transcript_data=transcript.fetch()
    transcript_text = " ".join([entry.text for entry in transcript_data])
    prompt = f"""
    다음 요리 영상 자막을 분석해서 1. 재료 이름, 2. 필요 수량, 3. 쇼핑몰 검색을 위한 최적의 키워드를 JSON 배열 형태로 추출해줘. 
    예: 'name': '양파', 'amount': '0.5개', 'search_keyword': '햇양파 1kg'
    자막 내용: {transcript_text}
    """
    response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[prompt],
        config=genai.types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json"
        )
    )
    search_text = json.loads(response.text)
    return search_text


import requests
from bs4 import BeautifulSoup
import json

headers = {
    "User-Agent": User-Agent,
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.kurly.com/"
}

url = f"https://api.kurly.com/search/v4/sites/market/normal-search?keyword=돼지+목살+스테이크용+500g&sortType=4&page=1"

res = requests.get(url, headers=headers)

if res.status_code == 200:
    data = res.json() # HTML이 아니라 JSON으로 바로 받기
