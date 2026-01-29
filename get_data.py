import os
import re
import pandas as pd
from datetime import datetime, timedelta
import googleapiclient.discovery
from google import genai


YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def is_korean(text):
    # 한글이 포함되어 있는지 확인 (영어만 있는 제목 제거)
    return bool(re.search('[가-힣]', text))


def filter_cooking_videos(candidate_list):
    # Gemini에게 보낼 텍스트 리스트 만들기
    titles_only = [f"{i}. {item['title']}" for i, item in enumerate(candidate_list)]
    titles_blob = "\n".join(titles_only)

    prompt = f"""
    아래는 유튜브 영상 제목 리스트이다. 
    이 중에서 '실제 요리 방법(레시피)'을 알려주는 영상만 골라내라.
    먹방, 리뷰, 단순 식당 소개, 요리와 관련 없는 영상은 제외해라.
    결과는 오직 해당 번호들만 쉼표로 구분해서 출력해라 (예: 1, 3, 5).

    리스트:
    {titles_blob}
    """
    response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[prompt],
        config=genai.types.GenerateContentConfig(
            temperature=0.0
        )
    )
    try:
        # 응답에서 번호들만 추출 (예: "1, 2, 5" -> [1, 2, 5])
        selected_indices = [int(idx.strip()) for idx in response.text.split(',')]
        
        # 3. 선택된 번호에 해당하는 원본 데이터만 반환
        filtered_list = [candidate_list[i] for i in selected_indices if i < len(candidate_list)]
        return filtered_list
    except:
        print("Gemini 응답 형식이 올바르지 않습니다. 원본을 반환합니다.")
        return candidate_list

def get_real_trending_cooking(youtube):
    # 1. 한국 전체 인기 차트 상위 100개를 가져옴 (할당량 단 1점!)
    request = youtube.videos().list(
        part="snippet,statistics",
        chart="mostPopular",
        regionCode="KR",
        videoCategoryId="26",
        maxResults=50 # 일단 50개 확인
    )
    response = request.execute()

    cooking_candidates = []
    
    # 요리 관련 핵심 키워드 (태그 및 제목 검사용)
    cooking_keywords = ['레시피', '요리', '음식', 'cooking', 'recipe', '만드는법', '반찬', '찌개']

    for item in response.get('items', []):
        title = item['snippet']['title']
        tags = item['snippet'].get('tags', []) # 영상에 달린 태그들
        
        # 제목이나 태그에 요리 키워드가 하나라도 있는지 검사
        is_cooking = any(kw in title for kw in cooking_keywords) or \
                     any(kw in "".join(tags) for kw in cooking_keywords)

        if is_cooking:
            cooking_candidates.append({
                'video_id': item['id'],
                'title': title,
                'view_count': int(item['statistics'].get('viewCount', 0))
            })
            
    return cooking_candidates


#최근 2주내 업로드된 요리 레시피 영상 중 조회수 상위
def get_twoweek_cooking(youtube):
    two_weeks_ago = (datetime.utcnow() - timedelta(days=14)).isoformat() + "Z"

    request = youtube.search().list(
        q="레시피 | 요리 | 만드는 법 | 황금레시피",
        part="snippet",
        publishedAfter=two_weeks_ago,
        order="viewCount",
        maxResults=50,
        type="video",
        videoCategoryId="22",
        regionCode="KR",
        relevanceLanguage="ko"
    )
    search_response = request.execute()
    video_ids = []
    video_titles = {} # ID별 제목 임시 저장용
    
    for item in search_response.get('items', []):
        title = item['snippet']['title']
        v_id = item['id']['videoId']
        
        if is_korean(title): 
            video_ids.append(v_id)
            video_titles[v_id] = title

    if not video_ids:
        return []

    stats_request = youtube.videos().list(
        part="statistics",
        id=",".join(video_ids)
    )
    stats_response = stats_request.execute()

    korean_raw_candidates = []
    for item in stats_response.get('items', []):
        v_id = item['id']
        korean_raw_candidates.append({
            'video_id': v_id,
            'title': video_titles[v_id],
            'view_count': int(item['statistics'].get('viewCount', 0)) 
        })

    return korean_raw_candidates



#메이저채널에서 가져오기
def get_popular_channel_cooking(youtube, channel_ids):
    two_weeks_ago = (datetime.utcnow() - timedelta(days=14)).isoformat() + "Z"
    recent_videos = []
    video_ids = []

    # 1. 10개 채널에서 2주 내 업로드된 video_id들만 먼저 수집
    for channel_id in channel_ids:
        request = youtube.activities().list(
            part="contentDetails,snippet",
            channelId=channel_id,
            publishedAfter=two_weeks_ago,
            maxResults=15
        )
        response = request.execute()

        for item in response.get('items', []):
            if item['snippet']['type'] == 'upload':
                video_ids.append(item['contentDetails']['upload']['videoId'])

    # 2. 수집된 ID들의 실시간 정보(Title, ViewCount) 가져오기 (50개씩 묶어서 요청)
    final_list = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        stats_req = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(chunk)
        ).execute()

        for item in stats_req.get('items', []):
            final_list.append({
                'video_id': item['id'],
                'title': item['snippet']['title'],
                'view_count': int(item['statistics'].get('viewCount', 0))
            })

    return final_list

# 일주일 summary 데이터
def week_summary(youtube):
    today = datetime.now()
    date_list = [(today - timedelta(days=i)).strftime('%Y%m%d') for i in range(8)]
    
    all_data = []
    for date in date_list:
        file_name = f"{date}video_view.csv"
        if os.path.exists(file_name):
            df = pd.read_csv(file_name)
            all_data.append(df)
            print(f"로드 성공: {file_name}")
        else:
            print(f"파일 없음: {file_name} (수집이 안 된 날짜일 수 있음)")
    
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        unique_ids = combined_df['video_id'].unique().tolist()
        current_stats = []
        
        # API는 한 번에 최대 50개까지만 조회가 가능하므로 끊어서 요청
        for i in range(0, len(unique_ids), 50):
            chunk = unique_ids[i:i+50]
            request = youtube.videos().list(
                part="statistics,snippet",
                id=",".join(chunk)
            )
            response = request.execute()
    
            for item in response.get('items', []):
                current_stats.append({
                    'video_id': item['id'],
                    'title': item['snippet']['title'],
                    'current_view': int(item['statistics'].get('viewCount', 0))
                })
        
        current_df = pd.DataFrame(current_stats)
        return current_df
    else:
        return pd.DataFrame()


if __name__ == "__main__":

    target_channels = [
        'UC0htUSwcxfSGNfK_5Q28JkA', 'UC0VR2v4TZeGcOrZHnmwbU_Q', 'UCtby6rJtBGgUm-2oD_E7bzw',
        'UCaAka9CN4naD3FzHX6AvpqA', 'UCN8CPzwkYiDVLZlgD4JQgJQ', 'UCemFUqq5jad1f258HrPS5rg',
        'UCTV5_Y5gbVua8PpbOsim9RQ', 'UCMXFSqYCTcB4iIJLwUJaBrQ', 'UC1g9JaEVLOFGhH8hpaK--Jg',
        'UCC9pQY_uaBSa0WOpMNJHbEQ'
    ]
    trending_30 = get_real_trending_cooking(youtube)
    twoweek_cooking = get_twoweek_cooking(youtube)
    candidate_list = get_popular_channel_cooking(youtube, target_channels)
    combined = trending_30 + twoweek_cooking + candidate_list
    unique_candidates = {}
    for item in combined:
        v_id = item['video_id']
        unique_candidates[v_id] = item
    final_candidates = list(unique_candidates.values())
    filter_video = filter_cooking_videos(final_candidates)
    df = pd.DataFrame(filter_video)
    df['recorded_at'] = datetime.now().strftime('%Y-%m-%d')
    today_str = datetime.now().strftime('%Y%m%d')
    file_path = f'{today_str}video_view.csv'
    df.to_csv(file_path, index=False, encoding='utf-8-sig')

    today_weekday = datetime.now().weekday()
    if today_weekday == 6: 
        week_summary_df=week_summary(youtube)
        if not week_summary_df.empty:
            summary_file_path = f'{today_str}view_summary.csv'
            week_summary_df.to_csv(summary_file_path, index=False, encoding='utf-8-sig')
