#생활라이프 영상중 mostPopular 영상
import secret_key as key
import googleapiclient.discovery
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
from datetime import datetime, timedelta
import re
# 🔑 발급받은 키를 여기에 넣으세요
YOUTUBE_API_KEY = key.youtube_api_key
GEMINI_API_KEY = key.gemini_api_key
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def is_korean(text):
    # 한글이 포함되어 있는지 확인 (영어만 있는 제목 제거)
    return bool(re.search('[가-힣]', text))

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

# 실행 예시
trending_30 = get_real_trending_cooking(youtube)



#최근 2주내 업로드된 요리 레시피 영상 중 조회수 상위

import googleapiclient.discovery
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
from datetime import datetime, timedelta
import re
YOUTUBE_API_KEY = key.youtube_api_key
GEMINI_API_KEY = key.gemini_api_key
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
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
    relevanceLanguage="ko" # 1차 언어 필터
)
youtube_search_response = request.execute()
korean_raw_candidates = []
for item in youtube_search_response['items']:
    title = item['snippet']['title']
    if is_korean(title): # 2차 한글 정규식 필터
        korean_raw_candidates.append({
            'video_id': item['id']['videoId'],
            'title': title
        })
titles_for_ai = "\n".join([f"{i}. {v['title']}" for i, v in enumerate(korean_raw_candidates)])
prompt = f"""
너는 요리 전문 큐레이터야. 아래 리스트에서 '실제로 사람이 먹는 음식을 만드는 요리 레시피'만 골라줘.

[제외 대상]
- 음식이 아닌 것 (인형, 장난감, 연애, 심리, 화나게 만드는 법 등)
- 사람이 먹을 수 없는 것

결과는 오직 선택된 번호들만 콤마(,)로 구분해서 한 줄로 출력해.
리스트:
{titles_for_ai}
"""
response = gemini_client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[prompt],
    config=genai.types.GenerateContentConfig(
        temperature=0.0
    )
)

summary_text = response.text.strip()
selected_indices = [int(x.strip()) for x in summary_text.split(',') if x.strip().isdigit()]

# 최종 리스트 생성
final_list = [korean_raw_candidates[i] for i in selected_indices if i < len(korean_raw_candidates)]



#메이저채널에서 가져오기
import datetime

def get_recent_videos_with_views(youtube, channel_ids):
    two_weeks_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=14)).isoformat() + "Z"
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

# --- 실행 및 결과 확인 ---
target_channels = [
    'UC0htUSwcxfSGNfK_5Q28JkA', 'UC0VR2v4TZeGcOrZHnmwbU_Q', 'UCtby6rJtBGgUm-2oD_E7bzw',
    'UCaAka9CN4naD3FzHX6AvpqA', 'UCN8CPzwkYiDVLZlgD4JQgJQ', 'UCemFUqq5jad1f258HrPS5rg',
    'UCTV5_Y5gbVua8PpbOsim9RQ', 'UCMXFSqYCTcB4iIJLwUJaBrQ', 'UC1g9JaEVLOFGhH8hpaK--Jg',
    'UCC9pQY_uaBSa0WOpMNJHbEQ'
]

# 기존과 똑같은 포맷으로 추출
candidate_list = get_recent_videos_with_views(youtube, target_channels)

for v in candidate_list:
    print(f"ID: {v['video_id']} | 조회수: {v['view_count']:,} | 제목: {v['title']}")
