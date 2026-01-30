import pandas as pd
from datetime import datetime, timedelta
import os
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
    merge_df['view_growth'] = merge_df['current_view'] - merge_df['start_view']
    top_20 = merge_df.sort_values(by='view_growth', ascending=False).head(20)
    return top_20
