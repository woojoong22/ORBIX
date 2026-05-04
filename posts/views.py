import json
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.conf import settings
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from PIL import Image

from .models import Category, ChatMessage, Post, PostComment, PostLike, PostMedia, Subscription, TopicBoard, UserProfile

MAX_CHAT_IMAGE_SIZE = 3 * 1024 * 1024
ALLOWED_CHAT_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MAX_PROFILE_PHOTO_SIZE = 3 * 1024 * 1024
MAX_POST_IMAGE_COUNT = 20
MAX_POST_IMAGE_SIZE = 3 * 1024 * 1024
MAX_POST_VIDEO_SIZE = 100 * 1024 * 1024
ALLOWED_POST_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
ALLOWED_POST_VIDEO_TYPES = {'video/mp4', 'video/webm', 'video/quicktime'}
OTHER_CATEGORY_NAME = '기타'


DEFAULT_TAXONOMY = {
    '취미': {
        '스포츠': ['축구', '야구', '농구', '러닝', '헬스', '등산', '자전거', '골프'],
        '문화예술': ['영화', '음악', '전시', '공연', '뮤지컬', '클래식', '책', '웹툰'],
        '창작': ['그림', '사진', '글쓰기', '영상 편집', '작곡', '공예', '디자인', '웹소설'],
        '게임': {
            'PC 게임': ['배틀그라운드', '리그 오브 레전드', '발로란트', '오버워치', '메이플스토리', '로스트아크', '피파온라인', '서든어택'],
            '콘솔 게임': ['플레이스테이션', '닌텐도 스위치', 'Xbox', '젤다', '포켓몬', '몬스터헌터', '파이널판타지'],
            '모바일 게임': ['원신', '붕괴 스타레일', '쿠키런', '브롤스타즈', '클래시 로얄', '모바일 RPG', '모바일 퍼즐'],
            'e스포츠': ['LCK', '발로란트 챔피언스', '오버워치 리그', '게임 대회', '프로게이머', '경기분석'],
            '스팀': ['스팀 할인', '인디게임', '생존게임', '시뮬레이션', '로그라이크', '멀티게임'],
            '보드게임': ['전략 보드게임', '파티게임', 'TRPG', '마작', '체스', '보드게임 모임'],
        },
        '라이프스타일': ['요리', '카페', '여행', '반려생활', '패션', '인테리어', '캠핑'],
        '수집/취향': ['시계', '향수', '문구', '피규어', 'LP', '빈티지', '키보드'],
    },
    '직업': {
        '전문직': ['의사', '변호사', '회계사', '약사', '세무사', '노무사', '변리사'],
        '취업': {
            '취업 일반': ['취업', '취준', '취업준비', '구직', '채용', '공채', '수시채용', '커리어', '이직'],
            '대기업': ['대기업', '삼성전자', '현대자동차', 'SK하이닉스', 'LG전자', '네이버', '카카오', 'CJ', '롯데', '포스코'],
            '공기업': ['공기업', '공공기관', '한국전력', '한전', '한국수력원자력', '한국도로공사', '코레일', 'LH', '건보', '국민건강보험공단'],
            '전문직': ['전문직 취업', '로스쿨', '회계사 취업', '세무사 취업', '약사 취업', '노무사 취업', '변리사 취업'],
            '서류/면접': ['자소서', '자기소개서', '이력서', '포트폴리오', '면접', '인적성', 'NCS', '코딩테스트'],
            '인턴/신입': ['인턴', '체험형 인턴', '채용형 인턴', '신입', '신입공채', '대졸공채'],
        },
        '건설': ['건축 설계', '토목', '조경', '시공', '감리', '인테리어', '도시계획'],
        'IT': ['개발자', '데이터', '보안', '인프라', '기획자', '디자이너', 'AI'],
        '마케팅': ['브랜딩', '퍼포먼스 마케팅', '콘텐츠 마케팅', 'SNS 운영', 'PR', '그로스'],
        '자영업': ['카페', '음식점', '온라인 쇼핑몰', '프랜차이즈', '무인매장', '배달창업'],
        '공공/사무': ['공무원', '인사', '회계', '총무', '법무', '영업관리'],
    },
    '투자': {
        '주식': ['국장 투자', '미장 투자', '배당주', '성장주', '가치주', 'ETF', '퀀트'],
        '부동산': ['아파트', '상가', '토지', '청약', '재개발', '경매', '월세투자'],
        '가상자산': ['비트코인', '알트코인', '온체인', 'DeFi', 'NFT', '스테이킹'],
        '연금/장기투자': ['연금저축', 'IRP', 'ISA', '노후준비', '자산배분', '리밸런싱'],
        '경제공부': ['기업분석', '재무제표', '경제지표', '투자일지', '리스크 관리'],
    },
    '생활': {
        '집/살림': ['청소', '정리수납', '가전', '가구', '셀프수리', '월세살이', '전세살이'],
        '패션/뷰티': ['데일리룩', '스킨케어', '메이크업', '헤어', '신발', '가방', '향수'],
        '자동차': ['국산차', '수입차', '전기차', '정비', '튜닝', '바이크', '중고차'],
        '쇼핑': ['핫딜', '직구', '가성비템', '명품', '중고거래', '구독서비스'],
    },
    '지역': {
        '서울': ['강남', '홍대', '성수', '잠실', '종로', '용산', '여의도'],
        '수도권': ['인천', '수원', '성남', '고양', '용인', '부천', '안양'],
        '영남': ['부산', '대구', '울산', '창원', '포항', '김해'],
        '호남/제주': ['광주', '전주', '여수', '목포', '제주', '서귀포'],
        '충청/강원': ['대전', '세종', '청주', '천안', '춘천', '강릉', '원주'],
    },
    '공부': {
        '입시': ['수능', '내신', '논술', '입시정보', '재수', '편입'],
        '외국어': ['영어', '일본어', '중국어', '스페인어', '토익', '회화'],
        '자격증': ['기사자격증', '컴활', '한국사', '공인중개사', '전산회계', 'SQLD'],
        '대학/전공': ['공대', '문과', '상경', '의약학', '예체능', '대학원'],
        '커리어학습': ['포트폴리오', '부트캠프', '스터디', '온라인 강의', '독학'],
    },
    '건강': {
        '운동': ['헬스', '필라테스', '요가', '러닝', '수영', '홈트'],
        '멘탈케어': ['스트레스', '불면', '명상', '상담', '번아웃', '자존감'],
        '질환/관리': ['피부', '치아', '목/허리', '눈 건강', '영양제', '검진'],
        '식단': ['다이어트', '벌크업', '저탄고지', '비건', '혈당관리', '간헐적 단식'],
    },
    '테크': {
        'AI': ['생성형 AI', '프롬프트', 'AI 서비스', '자동화', 'AI 뉴스', 'AI 이미지'],
        '기기': ['스마트폰', '노트북', '태블릿', '웨어러블', '카메라', '오디오'],
        '개발': ['웹개발', '앱개발', '백엔드', '프론트엔드', '오픈소스', 'DevOps'],
        '보안/인터넷': ['개인정보', '해킹', 'VPN', '클라우드', '홈서버', '네트워크'],
    },
    '엔터': {
        '연예': ['아이돌', '배우', '예능', '드라마', '팬덤', '시상식'],
        '콘텐츠': ['넷플릭스', '유튜브', 'OTT', '팟캐스트', '밈', '숏폼'],
        '음악': ['K팝', '힙합', '밴드', '인디', '플레이리스트', '공연후기'],
        '스포츠관람': ['KBO', 'K리그', 'NBA', 'EPL', 'UFC', '올림픽'],
    },
    '사회': {
        '뉴스': ['정치', '경제뉴스', '사회이슈', '국제뉴스', '정책', '선거'],
        '토론': ['찬반토론', '시사토론', '세대담론', '지역이슈', '미디어비평'],
        '공익': ['환경', '기부', '봉사', '동물권', '장애인권', '공공서비스'],
        '법/제도': ['생활법률', '노동법', '부동산법', '소비자권리', '민원'],
    },
    '관계': {
        '연애': ['썸', '장거리', '데이트', '이별', '소개팅', '결혼준비'],
        '가족': ['육아', '부모님', '형제자매', '반려가족', '명절', '가족갈등'],
        '친구/모임': ['친구관계', '동호회', '직장인 모임', '스터디모임', '인간관계'],
        '상담': ['고민상담', '진로고민', '직장고민', '관계회복', '익명상담'],
    },
    OTHER_CATEGORY_NAME: {
        OTHER_CATEGORY_NAME: [OTHER_CATEGORY_NAME],
    },
}

DEFAULT_TAXONOMY['패션'] = {
    '스타일/코디': ['데일리룩', '출근룩', '데이트룩', '하객룩', '여행룩', '스트릿', '미니멀', '빈티지'],
    '의류': ['아우터', '상의', '셔츠/블라우스', '니트', '팬츠', '스커트', '원피스', '셋업'],
    '신발': ['스니커즈', '로퍼', '부츠', '샌들', '힐/펌프스', '운동화', '구두 관리'],
    '가방': ['토트백', '숄더백', '크로스백', '백팩', '미니백', '클러치', '지갑/카드홀더'],
    '액세서리': ['주얼리', '모자', '벨트', '시계', '안경/선글라스', '스카프', '양말'],
    '브랜드/쇼핑': ['국내 브랜드', '디자이너 브랜드', 'SPA/패스트패션', '명품', '세일/핫딜', '중고/빈티지', '사이즈 후기'],
    '패션 케어': ['세탁/관리', '수선', '보관', '소재 정보', '향수', '옷장 정리'],
}

DEFAULT_TAXONOMY['음식'] = {
    '한식': ['집밥', '김치찌개', '된장찌개', '국/탕', '반찬', '분식', '김밥', '한식맛집'],
    '양식': ['파스타', '스테이크', '피자', '샐러드', '브런치', '버거', '양식맛집'],
    '중식/일식/아시안': ['중식', '일식', '초밥', '라멘', '쌀국수', '태국음식', '마라탕'],
    '요리/레시피': ['자취요리', '간편식', '면요리', '고기요리', '채식', '밀프렙', '에어프라이어'],
    '베이킹/디저트': ['베이킹', '케이크', '쿠키', '빵집', '디저트', '초콜릿', '아이스크림'],
    '맛집/외식': ['동네맛집', '웨이팅맛집', '혼밥', '데이트맛집', '가성비맛집', '파인다이닝', '푸드코트'],
    '카페/커피': ['카페투어', '원두/커피', '핸드드립', '에스프레소', '작업카페', '티/차', '브런치카페'],
    '술/음료': ['맥주', '와인', '위스키', '전통주', '칵테일', '논알콜', '안주', '음료'],
    '다이어트/건강식': ['다이어트 식단', '저탄고지', '고단백', '비건', '당뇨식', '도시락', '식단관리'],
    '식재료/장보기': ['장보기', '식재료보관', '제철음식', '정육/수산', '농산물', '양념/소스', '밀키트'],
    '주방도구/가전': ['조리도구', '주방가전', '칼/도마', '팬/냄비', '커피머신', '식기', '주방수납'],
}

DEFAULT_TAXONOMY['여행/아웃도어'] = {
    '국내여행': ['서울근교', '강원', '제주', '부산/경남', '전라', '충청', '당일치기'],
    '해외여행': ['일본', '동남아', '유럽', '미주', '중국/대만', '호주/뉴질랜드', '패키지'],
    '여행준비': ['항공권', '숙소', '여행일정', '환전/결제', '짐싸기', '여행보험', '비자'],
    '아웃도어': ['등산', '캠핑', '차박', '낚시', '자전거여행', '트레킹', '러닝코스'],
    '여행후기': ['맛집후기', '숙소후기', '교통후기', '사진스팟', '혼행', '가족여행'],
}

DEFAULT_TAXONOMY['자동차/모빌리티'] = {
    '차량구매': ['신차', '중고차', '시승기', '견적', '리스/렌트', '전기차', '하이브리드'],
    '정비/관리': ['엔진오일', '타이어', '세차', '보험', '블랙박스', '소모품', '수리후기'],
    '운전/교통': ['초보운전', '주차', '장거리운전', '교통법규', '사고대처', '운전습관'],
    '튜닝/용품': ['차량용품', '실내튜닝', '외장튜닝', '오디오', '캠핑카', '내비/하이패스'],
    '모빌리티': ['자전거', '킥보드', '오토바이', '대중교통', '카셰어링', '배달라이더'],
}

DEFAULT_TAXONOMY['육아/가족'] = {
    '임신/출산': ['임신준비', '태교', '출산준비', '산후조리', '육아용품', '병원후기'],
    '영유아': ['수면', '수유/이유식', '기저귀', '장난감', '어린이집', '발달', '건강관리'],
    '초등/교육': ['초등생활', '학원', '독서', '영어교육', '놀이학습', '방학계획'],
    '가족생활': ['부부대화', '가사분담', '부모님', '명절', '가족여행', '집안행사'],
    '돌봄/지원': ['돌봄서비스', '정부지원', '워킹맘/대디', '육아휴직', '시간관리'],
}

DEFAULT_TAXONOMY['반려동물'] = {
    '강아지': ['산책', '훈련', '사료', '간식', '미용', '건강', '입양'],
    '고양이': ['모래', '캣타워', '사료', '습식/간식', '놀이', '건강', '합사'],
    '소동물': ['햄스터', '토끼', '고슴도치', '파충류', '조류', '물생활', '곤충'],
    '펫케어': ['동물병원', '보험', '영양제', '행동교정', '분리불안', '노령동물'],
    '펫라이프': ['펫동반여행', '펫카페', '용품후기', '사진자랑', '임시보호', '실종/제보'],
}

DEFAULT_TAXONOMY['과학/지식'] = {
    '자연과학': ['물리', '화학', '생물', '천문', '지구과학', '기상', '해양'],
    '공학': ['기계', '전기전자', '재료', '항공우주', '로봇', '토목', '에너지'],
    '수학/통계': ['기초수학', '확률통계', '데이터분석', '퍼즐', '문제풀이', '수학사'],
    '인문지식': ['철학', '심리학', '언어', '종교', '윤리', '문학이론', '비평'],
    '지식공유': ['오늘배운것', '질문답변', '책요약', '강의추천', '논문읽기', '자료공유'],
}

DEFAULT_TAXONOMY['역사/문화'] = {
    '한국사': ['고대/삼국', '고려', '조선', '근현대', '지역사', '인물사'],
    '세계사': ['동아시아', '유럽', '미국', '중동', '전쟁사', '문명사', '역사지도'],
    '문화유산': ['박물관', '유적지', '전통문화', '민속', '궁궐', '문화재'],
    '언어/번역': ['한국어', '영어', '일본어', '중국어', '번역질문', '어원'],
    '토론': ['역사해석', '책추천', '다큐추천', '전시후기', '문화비평'],
}

DEFAULT_TAXONOMY['메이커/DIY'] = {
    '집수리': ['공구', '페인트', '전기작업', '수전/배관', '가구수리', '방음/단열'],
    '목공/공예': ['목공', '가죽공예', '도자기', '뜨개질', '레진', '금속공예', '업사이클'],
    '전자/하드웨어': ['아두이노', '라즈베리파이', '센서', '3D프린팅', '납땜', '키보드'],
    '창작도구': ['작업실', '재료구매', '도면/설계', '제작후기', '안전수칙'],
    '작품공유': ['완성작', '제작과정', '실패담', '의뢰/협업', '전시/마켓'],
}

DEFAULT_TAXONOMY['쇼핑/거래'] = {
    '핫딜': ['오늘의딜', '쿠폰', '카드할인', '직구딜', '가격비교', '품절/재입고'],
    '구매후기': ['생활용품', '전자제품', '패션잡화', '가전', '가구', '식품'],
    '중고거래': ['거래팁', '사기예방', '가격문의', '나눔', '직거래', '택배거래'],
    '직구/배송': ['아마존', '알리', '배대지', '관세', '배송조회', '반품/환불'],
    '소비생활': ['구독서비스', '멤버십', '포인트', '절약팁', '가계부', '미니멀소비'],
}

DEFAULT_TAXONOMY['인터넷문화'] = {
    '밈/유머': ['짤방', '드립', '유행어', '패러디', '인터넷밈', '웃긴글'],
    '크리에이터': ['유튜버', '스트리머', '팟캐스트', '라이브방송', '팬커뮤니티'],
    'SNS': ['인스타그램', '틱톡', 'X/트위터', '블로그', '커뮤니티운영', '알고리즘'],
    '디지털생활': ['앱추천', '웹서비스', '생산성도구', '온라인보안', '디지털정리'],
    '이슈/트렌드': ['화제의글', '바이럴', '챌린지', '온라인논쟁', '플랫폼소식'],
}

SAMPLE_POSTS = [
    {
        'title': '개인 피드와 주제 게시판이 함께 흐릅니다',
        'content': '글은 주제 게시판에 올라가면서 작성자의 개인 피드에도 남습니다.',
    },
    {
        'title': '채팅은 익명 또는 실명으로 참여할 수 있습니다',
        'content': '실명 모드는 개인 피드 이름으로 표시되고, 익명 모드는 사용자 정보를 숨깁니다.',
    },
]


TOPIC_ICON_OVERRIDES = {
    '취미': '⚽',
    '직업': '💼',
    '투자': '📈',
    '생활': '🏠',
    '지역': '📍',
    '공부': '📚',
    '건강': '💪',
    '테크': '🎮',
    '엔터': '🎵',
    '사회': '📰',
    '관계': '💬',
    '패션': '👗',
    '음식': '🍽️',
    '여행/아웃도어': '🏕️',
    '자동차/모빌리티': '🚗',
    '육아/가족': '👶',
    '반려동물': '🐶',
    '과학/지식': '🔬',
    '역사/문화': '🏛️',
    '메이커/DIY': '🛠️',
    '쇼핑/거래': '🛒',
    '인터넷문화': '🌐',
    '스포츠': '⚽',
    '축구': '⚽',
    '야구': '⚾',
    '농구': '🏀',
    '러닝': '🏃',
    '헬스': '🏋️',
    '등산': '🥾',
    '자전거': '🚴',
    '골프': '⛳',
    '문화예술': '🎨',
    '영화': '🎬',
    '음악': '🎧',
    '전시': '🖼️',
    '공연': '🎭',
    '뮤지컬': '🎼',
    '클래식': '🎻',
    '책': '📖',
    '웹툰': '💬',
    '창작': '✍️',
    '그림': '🎨',
    '사진': '📷',
    '글쓰기': '✍️',
    '영상 편집': '🎞️',
    '작곡': '🎹',
    '공예': '🧶',
    '디자인': '🖌️',
    '웹소설': '📚',
    'PC 게임': '🖥️',
    '배틀그라운드': '🪂',
    '리그 오브 레전드': '🛡️',
    '발로란트': '🎯',
    '오버워치': '🦾',
    '메이플스토리': '🍁',
    '로스트아크': '⚓',
    '피파온라인': '⚽',
    '서든어택': '🔫',
    '콘솔 게임': '🕹️',
    '플레이스테이션': '🎮',
    '닌텐도 스위치': '🔴',
    'Xbox': '🟢',
    '젤다': '🗡️',
    '포켓몬': '🔴',
    '몬스터헌터': '🐉',
    '파이널판타지': '💎',
    '모바일 게임': '📱',
    '원신': '✨',
    '붕괴 스타레일': '🚂',
    '쿠키런': '🍪',
    '브롤스타즈': '⭐',
    '클래시 로얄': '👑',
    'e스포츠': '🎮',
    'LCK': '🏆',
    '발로란트 챔피언스': '🏆',
    '게임 대회': '🏟️',
    '프로게이머': '🎧',
    '경기분석': '📊',
    '스팀': '♨️',
    '스팀 할인': '🏷️',
    '인디게임': '💡',
    '생존게임': '🏕️',
    '시뮬레이션': '🧪',
    '로그라이크': '🌀',
    '멀티게임': '👥',
    '보드게임': '🎲',
    '전략 보드게임': '♟️',
    '파티게임': '🎉',
    'TRPG': '📜',
    '마작': '🀄',
    '체스': '♟️',
    '보드게임 모임': '👥',
    '라이프스타일': '🌿',
    '요리': '🍳',
    '카페': '☕',
    '여행': '🧳',
    '반려생활': '🐾',
    '인테리어': '🛋️',
    '캠핑': '🏕️',
    '수집/취향': '🧩',
    '시계': '⌚',
    '향수': '🧴',
    '문구': '🖊️',
    '피규어': '🧸',
    'LP': '💿',
    '빈티지': '🧥',
    '키보드': '⌨️',
    '전문직': '🧑‍⚕️',
    '건설': '🏗️',
    'IT': '💻',
    '자영업': '🏪',
    '공공/사무': '🗂️',
    '가상자산': '🪙',
    '연금/장기투자': '🏦',
    '경제공부': '📚',
    '집/살림': '🏠',
    '패션/뷰티': '👗',
    '데일리룩': '👕',
    '스킨케어': '🧴',
    '메이크업': '💄',
    '헤어': '💇',
    '신발': '👟',
    '가방': '👜',
    '귀마개': '🧤',
    '교육': '🎓',
    '자격증': '🏅',
    '외국어': '🗣️',
    '입시': '🎒',
    '독서/노트': '📚',
    '운동': '💪',
    '필라테스': '🤸',
    '요가': '🧘',
    '수영': '🏊',
    '홈트': '🏠',
    '의료': '🏥',
    '멘탈케어': '🧘',
    '뉴스/시사': '📰',
    '법/제도': '⚖️',
    '고민': '💬',
    '한식': '🥘',
    '집밥': '🍚',
    '김치찌개': '🥘',
    '된장찌개': '🍲',
    '국/탕': '🍲',
    '반찬': '🥗',
    '분식': '🍢',
    '김밥': '🍙',
    '양식': '🍝',
    '파스타': '🍝',
    '스테이크': '🥩',
    '피자': '🍕',
    '샐러드': '🥗',
    '브런치': '🥞',
    '버거': '🍔',
    '중식/일식/아시안': '🥢',
    '중식': '🥟',
    '일식': '🍣',
    '초밥': '🍣',
    '라멘': '🍜',
    '쌀국수': '🍜',
    '마라탕': '🌶️',
    '요리/레시피': '📋',
    '자취요리': '🍳',
    '간편식': '🍱',
    '면요리': '🍜',
    '고기요리': '🥩',
    '채식': '🥬',
    '에어프라이어': '♨️',
    '베이킹/디저트': '🧁',
    '베이킹': '🥐',
    '케이크': '🍰',
    '쿠키': '🍪',
    '빵집': '🥐',
    '디저트': '🧁',
    '아이스크림': '🍨',
    '맛집/외식': '🍽️',
    '혼밥': '🍱',
    '파인다이닝': '🍷',
    '카페/커피': '☕',
    '카페투어': '☕',
    '원두/커피': '🫘',
    '핸드드립': '☕',
    '에스프레소': '☕',
    '티/차': '🍵',
    '술/음료': '🍹',
    '맥주': '🍺',
    '와인': '🍷',
    '위스키': '🥃',
    '칵테일': '🍸',
    '안주': '🍢',
    '다이어트/건강식': '🥗',
    '다이어트 식단': '🥗',
    '고단백': '🥚',
    '비건': '🥬',
    '도시락': '🍱',
    '식재료/장보기': '🛒',
    '장보기': '🛒',
    '정육/수산': '🥩',
    '농산물': '🥕',
    '밀키트': '📦',
    '주방도구/가전': '🍳',
    '조리도구': '🥄',
    '주방가전': '🔌',
    '커피머신': '☕',
    '국내여행': '🚄',
    '해외여행': '✈️',
    '여행준비': '🧳',
    '아웃도어': '🥾',
    '차박': '🚙',
    '낚시': '🎣',
    '자전거여행': '🚴',
    '트레킹': '🥾',
    '러닝코스': '🏃',
    '여행후기': '🗺️',
    '숙소후기': '🏨',
    '사진스팟': '📷',
    '차량구매': '🚗',
    '신차': '🚘',
    '중고차': '🚙',
    '전기차': '🔋',
    '하이브리드': '🌿',
    '정비/관리': '🔧',
    '엔진오일': '🛢️',
    '타이어': '🛞',
    '세차': '🧽',
    '보험': '🛡️',
    '운전/교통': '🛣️',
    '초보운전': '🚗',
    '주차': '🅿️',
    '교통법규': '🚦',
    '튜닝/용품': '🛠️',
    '차량용품': '🧰',
    '캠핑카': '🚐',
    '모빌리티': '🛴',
    '킥보드': '🛴',
    '오토바이': '🏍️',
    '대중교통': '🚌',
    'AI 서비스': '🤖',
    '생성형 AI': '✨',
    '프롬프트': '💬',
    '자동화': '⚙️',
    'AI 뉴스': '📰',
    'AI 이미지': '🖼️',
    '기기': '📱',
    '스마트폰': '📱',
    '노트북': '💻',
    '태블릿': '📱',
    '웨어러블': '⌚',
    '카메라': '📷',
    '오디오': '🎧',
    '웹개발': '🌐',
    '앱개발': '📱',
    '백엔드': '🧱',
    '프론트엔드': '🎨',
    '오픈소스': '🧩',
    'DevOps': '🚀',
    '보안/인터넷': '🔐',
    '개인정보': '🪪',
    '해킹': '🛡️',
    'VPN': '🔒',
    '클라우드': '☁️',
    '홈서버': '🖥️',
    '네트워크': '🕸️',
    OTHER_CATEGORY_NAME: '⋯',
}


TOPIC_ICON_KEYWORDS = (
    ('축구', '⚽'), ('야구', '⚾'), ('농구', '🏀'), ('러닝', '🏃'), ('헬스', '💪'), ('등산', '⛰️'),
    ('게임', '🎮'), ('음악', '🎵'), ('영화', '🎬'), ('드라마', '📺'), ('공연', '🎭'), ('독서', '📚'),
    ('개발', '💻'), ('AI', '🤖'), ('데이터', '📊'), ('보안', '🔐'), ('마케팅', '📣'), ('디자인', '🎨'),
    ('주식', '📈'), ('코인', '🪙'), ('부동산', '🏢'), ('재테크', '💰'), ('경제', '💹'),
    ('요리', '🍳'), ('맛집', '🍽️'), ('카페', '☕'), ('디저트', '🍰'), ('주류', '🍷'), ('와인', '🍷'), ('맥주', '🍺'), ('음료', '🥤'),
    ('여행', '🧭'), ('국내', '🚄'), ('해외', '✈️'), ('캠핑', '🏕️'), ('낚시', '🎣'), ('아웃도어', '🥾'),
    ('자동차', '🚗'), ('차량', '🚗'), ('정비', '🔧'), ('튜닝', '🛠️'), ('운전', '🛣️'), ('바이크', '🏍️'),
    ('육아', '👶'), ('가족', '👨‍👩‍👧'), ('임신', '🤰'), ('교육', '🎒'), ('돌봄', '🤝'),
    ('강아지', '🐶'), ('고양이', '🐱'), ('반려', '🐾'), ('펫', '🐾'),
    ('과학', '🔬'), ('수학', '∑'), ('공학', '⚙️'), ('인문', '🧠'), ('역사', '🏛️'), ('문화', '🏺'),
    ('목공', '🪚'), ('공예', '🧶'), ('DIY', '🛠️'), ('집수리', '🔨'), ('전자', '🔌'),
    ('쇼핑', '🛒'), ('핫딜', '🏷️'), ('중고', '♻️'), ('후기', '⭐'), ('직구', '📦'),
    ('밈', '😄'), ('유머', '😄'), ('SNS', '#'), ('크리에이터', '▶'), ('이슈', '🔥'), ('트렌드', '✨'),
    ('청소', '🧹'), ('가전', '🔌'), ('패션', '👗'), ('뷰티', '💄'), ('지역', '📍'), ('맛', '🍽️'),
    ('병원', '🏥'), ('운동', '💪'), ('심리', '🧘'), ('법', '⚖️'), ('뉴스', '📰'), ('상담', '💬'),
)


def get_topic_icon(name):
    if name in TOPIC_ICON_OVERRIDES:
        return TOPIC_ICON_OVERRIDES[name]
    for keyword, icon in TOPIC_ICON_KEYWORDS:
        if keyword in name:
            return icon
    return '▣'


def is_taxonomy_branch(value):
    return isinstance(value, dict)


def get_category_ancestors(category):
    ancestors = []
    current = category
    while current:
        ancestors.append(current)
        current = current.parent
    return list(reversed(ancestors))


def get_category_path_names(category):
    return [item.name for item in get_category_ancestors(category)]


def get_category_path_label(category):
    return ' > '.join(get_category_path_names(category))


def iter_taxonomy_leaf_options(branch=None, path=()):
    branch = DEFAULT_TAXONOMY if branch is None else branch
    for name, value in branch.items():
        if name == OTHER_CATEGORY_NAME:
            continue
        next_path = (*path, name)
        if is_taxonomy_branch(value):
            yield from iter_taxonomy_leaf_options(value, next_path)
        else:
            yield next_path, value


def get_taxonomy_value_for_path(path):
    if not path:
        return DEFAULT_TAXONOMY
    current = DEFAULT_TAXONOMY
    for name in path:
        if not is_taxonomy_branch(current) or name not in current:
            return None
        current = current[name]
    return current


def get_taxonomy_value_for_category(category):
    return get_taxonomy_value_for_path(get_category_path_names(category))


def get_taxonomy_presets_for_category(category):
    value = get_taxonomy_value_for_category(category)
    if is_taxonomy_branch(value):
        return []
    return value or []


def get_or_create_category_path(*path):
    if not path:
        return None
    parent = None
    category = None
    for depth, name in enumerate(path):
        if depth == 0:
            order = list(DEFAULT_TAXONOMY.keys()).index(name) + 1 if name in DEFAULT_TAXONOMY else len(DEFAULT_TAXONOMY) + 1
        else:
            order = parent.children.count() + 1
        category, _ = Category.objects.get_or_create(
            name=name,
            parent=parent,
            defaults={'order': order},
        )
        parent = category
    return category


def ensure_taxonomy_branch(parent, branch):
    for order, (name, value) in enumerate(branch.items(), start=1):
        category, _ = Category.objects.get_or_create(
            name=name,
            parent=parent,
            defaults={'order': order},
        )
        if category.order != order:
            category.order = order
            category.save(update_fields=['order'])
        if is_taxonomy_branch(value):
            ensure_taxonomy_branch(category, value)


def ensure_default_taxonomy():
    taxonomy_items = [
        item for item in DEFAULT_TAXONOMY.items()
        if item[0] != OTHER_CATEGORY_NAME
    ]
    if OTHER_CATEGORY_NAME in DEFAULT_TAXONOMY:
        taxonomy_items.append((OTHER_CATEGORY_NAME, DEFAULT_TAXONOMY[OTHER_CATEGORY_NAME]))

    for major_order, (major_name, subcategories) in enumerate(taxonomy_items, start=1):
        major, _ = Category.objects.get_or_create(
            name=major_name,
            parent=None,
            defaults={'order': major_order},
        )
        if major.order != major_order:
            major.order = major_order
            major.save(update_fields=['order'])
        ensure_taxonomy_branch(major, subcategories)


def ensure_profile(user):
    if not user.is_authenticated:
        return None
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'display_name': user.username},
    )
    return profile


def make_unique_slug(name):
    base = slugify(name, allow_unicode=True) or 'board'
    slug = base
    while TopicBoard.objects.filter(slug=slug).exists():
        slug = f'{base}-{uuid4().hex[:6]}'
    return slug


def get_or_create_board(category, name):
    try:
        return TopicBoard.objects.get_or_create(
            category=category,
            name=name,
            defaults={'slug': make_unique_slug(name)},
        )[0]
    except IntegrityError:
        return TopicBoard.objects.get(category=category, name=name)


BOARD_CATEGORY_RULES = (
    (
        '투자',
        '가상자산',
        (
            '비트코인', 'bitcoin', 'btc', '이더리움', 'ethereum', 'eth', '코인',
            '가상자산', '암호화폐', '블록체인', '알트코인', '리플', 'xrp',
            '솔라나', 'solana', '업비트', '빗썸', '바이낸스', 'nft', 'defi',
        ),
    ),
    (
        '쇼핑/거래',
        '공동구매',
        (
            '공동구매', '공구', '단체구매', '같이구매', '구매모집', '공동 주문',
            '공동주문', '묶음구매',
        ),
    ),
    (
        '쇼핑/거래',
        '핫딜',
        ('핫딜', '특가', '쿠폰', '할인', '최저가', '딜'),
    ),
    (
        '쇼핑/거래',
        '중고거래',
        ('중고', '당근', '거래', '나눔', '판매', '삽니다', '팝니다'),
    ),
    (
        '음식',
        '맛집/외식',
        ('맛집', '식당', '밥집', '맛집추천', '혼밥', '데이트맛집'),
    ),
    (
        '음식',
        '카페/커피',
        ('카페', '커피', '디저트', '베이커리', '빵집', '케이크'),
    ),
    (
        '음식',
        '한식',
        ('김치찌개', '된장찌개', '국밥', '떡볶이', '김밥', '한식'),
    ),
    (
        '음식',
        '요리/레시피',
        ('레시피', '요리', '집밥', '자취요리', '밀프렙', '에어프라이어'),
    ),
    (
        '음식',
        '술/음료',
        ('맥주', '와인', '위스키', '소주', '전통주', '칵테일', '음료'),
    ),
)


BOARD_CATEGORY_OVERRIDES = {
    '취업': ('직업', '취업', '취업 일반'),
    '구직': ('직업', '취업', '취업 일반'),
    '채용': ('직업', '취업', '취업 일반'),
    '취준': ('직업', '취업', '취업 일반'),
    '취업준비': ('직업', '취업', '취업 일반'),
    '대기업': ('직업', '취업', '대기업'),
    '삼성전자': ('직업', '취업', '대기업'),
    '공기업': ('직업', '취업', '공기업'),
    '공공기관': ('직업', '취업', '공기업'),
    '전문직 취업': ('직업', '취업', '전문직'),
    '면접': ('직업', '취업', '서류/면접'),
    '자소서': ('직업', '취업', '서류/면접'),
    '이력서': ('직업', '취업', '서류/면접'),
    '인턴': ('직업', '취업', '인턴/신입'),
    '캠핑': ('여행/아웃도어', '아웃도어'),
    '귀마개': ('패션', '액세서리'),
    '배틀그라운드': ('취미', '게임', 'PC 게임'),
    '배그': ('취미', '게임', 'PC 게임'),
    '리그 오브 레전드': ('취미', '게임', 'PC 게임'),
    '롤': ('취미', '게임', 'PC 게임'),
    '발로란트': ('취미', '게임', 'PC 게임'),
    '오버워치': ('취미', '게임', 'PC 게임'),
    '메이플스토리': ('취미', '게임', 'PC 게임'),
    '메이플': ('취미', '게임', 'PC 게임'),
    '로스트아크': ('취미', '게임', 'PC 게임'),
    '로아': ('취미', '게임', 'PC 게임'),
    '카페': ('음식', '카페/커피'),
    '커피': ('음식', '카페/커피'),
    '디저트': ('음식', '베이킹/디저트'),
    '맛집': ('음식', '맛집/외식'),
    '식당': ('음식', '맛집/외식'),
    '다이어트 식단': ('음식', '다이어트/건강식'),
    '식단': ('음식', '다이어트/건강식'),
}


GENERIC_OVERRIDE_KEYWORDS = {'취업', '구직', '채용', '취준', '면접', '자소서', '이력서', '인턴'}


def get_or_create_subcategory(major_name, subcategory_name):
    return get_or_create_category_path(major_name, subcategory_name)


def iter_taxonomy_options():
    yield from iter_taxonomy_leaf_options()


def infer_board_category_from_presets(board_name):
    normalized = board_name.casefold().strip()
    compact = ''.join(normalized.split())
    override = BOARD_CATEGORY_OVERRIDES.get(normalized) or BOARD_CATEGORY_OVERRIDES.get(compact)
    if not override:
        for keyword, category_path in sorted(BOARD_CATEGORY_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
            if keyword in GENERIC_OVERRIDE_KEYWORDS:
                continue
            keyword_compact = ''.join(keyword.casefold().split())
            if len(keyword_compact) >= 2 and keyword_compact in compact:
                override = category_path
                break
    if override:
        return get_valid_taxonomy_category(*override)
    best_match = None
    best_match_length = 0
    for category_path, presets in iter_taxonomy_options():
        for preset in presets:
            preset_normalized = preset.casefold().strip()
            preset_compact = ''.join(preset_normalized.split())
            if (
                normalized == preset_normalized or
                compact == preset_compact or
                len(preset_compact) >= 2 and preset_compact in compact
            ):
                if len(preset_compact) > best_match_length:
                    best_match = category_path
                    best_match_length = len(preset_compact)
    if best_match:
        return get_valid_taxonomy_category(*best_match)
    return None


def get_taxonomy_option_pairs():
    return [
        {'path': list(category_path), 'label': ' > '.join(category_path)}
        for category_path, _ in iter_taxonomy_options()
    ]


def get_valid_taxonomy_category(*path):
    path = tuple(item for item in path if item)
    if not path:
        return None
    value = get_taxonomy_value_for_path(path)
    if value is None:
        return None
    return get_or_create_category_path(*path)


def parse_openai_category_response(data):
    output_text = data.get('output_text', '')
    if output_text:
        return json.loads(output_text)
    for item in data.get('output', []):
        for content in item.get('content', []):
            if content.get('type') in {'output_text', 'text'} and content.get('text'):
                return json.loads(content['text'])
    return {}


def infer_board_category_with_ai(board_name):
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        return None

    options = get_taxonomy_option_pairs()
    payload = {
        'model': getattr(settings, 'OPENAI_CATEGORY_MODEL', 'gpt-4.1-mini'),
        'input': [
            {
                'role': 'system',
                'content': (
                    'You classify Korean community board names into one existing taxonomy option. '
                    'Choose only from the provided options. Return JSON only.'
                ),
            },
            {
                'role': 'user',
                'content': json.dumps({
                    'board_name': board_name,
                    'options': options,
                    'instructions': (
                        'Pick the most semantically relevant taxonomy path. '
                        'If uncertain, set confidence below 0.65.'
                    ),
                }, ensure_ascii=False),
            },
        ],
        'text': {
            'format': {
                'type': 'json_schema',
                'name': 'board_category_route',
                'schema': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'path': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'minItems': 2,
                        },
                        'confidence': {'type': 'number'},
                        'reason': {'type': 'string'},
                    },
                    'required': ['path', 'confidence', 'reason'],
                },
                'strict': True,
            },
        },
    }
    request = Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))
        result = parse_openai_category_response(data)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
        return None

    if float(result.get('confidence', 0)) < 0.65:
        return None
    return get_valid_taxonomy_category(*result.get('path', []))


def infer_board_category(board_name):
    preset_category = infer_board_category_from_presets(board_name)
    if preset_category:
        return preset_category
    normalized = board_name.casefold()
    for major_name, subcategory_name, keywords in BOARD_CATEGORY_RULES:
        if any(keyword.casefold() in normalized for keyword in keywords):
            return get_or_create_subcategory(major_name, subcategory_name)
    return infer_board_category_with_ai(board_name)


def get_auto_routed_category(fallback_category, board_name):
    if not should_auto_route_board(fallback_category):
        return None
    return infer_board_category(board_name)


def is_hangul_syllable(char):
    return 0xAC00 <= ord(char) <= 0xD7A3


def is_hangul_jamo(char):
    codepoint = ord(char)
    return 0x1100 <= codepoint <= 0x11FF or 0x3130 <= codepoint <= 0x318F


def is_meaningful_board_name(board_name):
    compact = ''.join(board_name.split())
    if len(compact) < 2:
        return False
    if any(is_hangul_jamo(char) for char in compact):
        return False
    allowed_punctuation = {'-', '/', '&', '+'}
    if not all(
        is_hangul_syllable(char) or
        char.isascii() and char.isalpha() or
        char.isdigit() or
        char in allowed_punctuation
        for char in compact
    ):
        return False
    has_hangul = any(is_hangul_syllable(char) for char in compact)
    letters = [char for char in compact if char.isascii() and char.isalpha()]
    digits = [char for char in compact if char.isdigit()]
    if has_hangul:
        return True
    if letters and not digits and len(letters) >= 3:
        return True
    return False


def should_auto_route_board(fallback_category):
    return (
        fallback_category.name == OTHER_CATEGORY_NAME or
        (fallback_category.parent and fallback_category.parent.name == OTHER_CATEGORY_NAME)
    )


def get_or_create_routed_board(fallback_category, board_name):
    if not is_meaningful_board_name(board_name):
        return None
    routed_category = get_auto_routed_category(fallback_category, board_name)
    category = routed_category or fallback_category
    existing_board = TopicBoard.objects.filter(name=board_name).first()
    if existing_board:
        if routed_category and existing_board.category_id != routed_category.id:
            existing_board.category = routed_category
            existing_board.save(update_fields=['category'])
        return existing_board
    return get_or_create_board(category, board_name)


def get_other_category():
    major, _ = Category.objects.get_or_create(
        name=OTHER_CATEGORY_NAME,
        parent=None,
        defaults={'order': len(DEFAULT_TAXONOMY)},
    )
    other_order = len(DEFAULT_TAXONOMY)
    if major.order != other_order:
        major.order = other_order
        major.save(update_fields=['order'])
    other, _ = Category.objects.get_or_create(
        name=OTHER_CATEGORY_NAME,
        parent=major,
        defaults={'order': 1},
    )
    return other


def build_category_tree():
    def build_node(category):
        children = [build_node(child) for child in category.children.all()]
        presets = get_taxonomy_presets_for_category(category)
        return {
            'category': category,
            'icon': get_topic_icon(category.name),
            'children': children,
            'presets': [
                {'name': preset, 'icon': get_topic_icon(preset)}
                for preset in presets
            ],
            'preset_names': presets,
            'boards': [
                {'board': board, 'icon': get_topic_icon(board.name)}
                for board in category.boards.all()[:8]
            ],
        }

    tree = []
    taxonomy_items = [
        item for item in DEFAULT_TAXONOMY.items()
        if item[0] != OTHER_CATEGORY_NAME
    ]
    if OTHER_CATEGORY_NAME in DEFAULT_TAXONOMY:
        taxonomy_items.append((OTHER_CATEGORY_NAME, DEFAULT_TAXONOMY[OTHER_CATEGORY_NAME]))

    for major_name, subcategories in taxonomy_items:
        try:
            major = Category.objects.prefetch_related(
                'children__children__boards',
                'children__boards',
                'boards',
            ).get(
                name=major_name,
                parent__isnull=True,
            )
        except Category.DoesNotExist:
            continue

        tree.append(build_node(major))
    return tree


def get_topic_cards(topic_category):
    if not topic_category:
        return [
            {'category': category, 'icon': get_topic_icon(category.name)}
            for category in Category.objects.filter(parent__isnull=True).order_by('order', 'name')
        ]
    return [{'category': topic_category, 'icon': get_topic_icon(topic_category.name), 'active': True}]


def get_topic_back_category(topic_category):
    if not topic_category:
        return None
    return topic_category.parent


def get_subtopic_items(topic_category, selected_board=None):
    if not topic_category:
        return []
    items = []
    for child in topic_category.children.all().order_by('order', 'name'):
        items.append({
            'type': 'category',
            'category': child,
            'name': child.name,
            'icon': get_topic_icon(child.name),
            'active': False,
        })
    preset_names = get_taxonomy_presets_for_category(topic_category)
    for preset in preset_names:
        items.append({
            'type': 'preset',
            'category': topic_category,
            'name': preset,
            'icon': get_topic_icon(preset),
            'selected': bool(selected_board and selected_board.name == preset),
        })
    for board in topic_category.boards.all()[:12]:
        if board.name in preset_names:
            continue
        items.append({
            'type': 'board',
            'board': board,
            'name': board.name,
            'icon': get_topic_icon(board.name),
            'selected': bool(selected_board and selected_board.id == board.id),
        })
    return items


def get_descendant_category_ids(category):
    ids = [category.id]
    pending = list(category.children.all())
    while pending:
        child = pending.pop()
        ids.append(child.id)
        pending.extend(list(child.children.all()))
    return ids


def get_selected_board(request):
    board_slug = request.GET.get('board')
    if board_slug:
        return get_object_or_404(TopicBoard, slug=board_slug)
    return None


def get_selected_category(request):
    category_id = request.GET.get('category')
    if category_id:
        return get_object_or_404(Category, id=category_id)
    return None


def get_valid_chat_image(request):
    image = request.FILES.get('image')
    if not image:
        return None
    if image.size > MAX_CHAT_IMAGE_SIZE:
        return None
    if getattr(image, 'content_type', '') not in ALLOWED_CHAT_IMAGE_TYPES:
        return None
    return image


def get_valid_profile_photo(request):
    photo = request.FILES.get('photo')
    if not photo:
        return None
    if photo.size > MAX_PROFILE_PHOTO_SIZE:
        return None
    if getattr(photo, 'content_type', '') not in ALLOWED_CHAT_IMAGE_TYPES:
        return None
    return photo


def get_chat_context(request, selected_board=None, selected_category=None):
    chat_scope = request.GET.get('chat')
    private_user = None
    if chat_scope == 'private' and request.user.is_authenticated:
        private_user = User.objects.filter(id=request.GET.get('private_user')).first()
        if not private_user or private_user == request.user:
            chat_scope = 'global'
            private_user = None
    elif chat_scope == 'category' and selected_category:
        pass
    elif selected_board:
        chat_scope = 'board'
    elif selected_category:
        chat_scope = 'category'
    else:
        chat_scope = 'global'

    chat_messages = ChatMessage.objects.select_related(
        'user',
        'user__profile',
        'board',
        'category',
        'recipient',
        'recipient__profile',
    )
    if chat_scope == 'private' and private_user:
        chat_messages = chat_messages.filter(
            Q(user=request.user, recipient=private_user) |
            Q(user=private_user, recipient=request.user)
        )
        chat_title = f'{private_user.profile.display_name if hasattr(private_user, "profile") else private_user.username} 개인채팅'
    elif chat_scope == 'category' and selected_category:
        chat_messages = chat_messages.filter(
            category=selected_category,
            board__isnull=True,
            recipient__isnull=True,
        )
        chat_title = f'{selected_category.name} 채팅'
    elif chat_scope == 'board' and selected_board:
        chat_messages = chat_messages.filter(
            board=selected_board,
            category__isnull=True,
            recipient__isnull=True,
        )
        chat_title = f'{selected_board.name} 채팅'
    else:
        chat_scope = 'global'
        chat_messages = chat_messages.filter(
            board__isnull=True,
            category__isnull=True,
            recipient__isnull=True,
        )
        chat_title = '전체 채팅'

    return {
        'chat_scope': chat_scope,
        'private_user': private_user,
        'chat_title': chat_title,
        'chat_messages': reversed(list(chat_messages.order_by('-created_at')[:30])),
    }


def compress_image(uploaded_file):
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    image.load()
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')

    image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
    quality = 85
    buffer = BytesIO()
    while quality >= 55:
        buffer.seek(0)
        buffer.truncate()
        image.save(buffer, format='JPEG', quality=quality, optimize=True)
        if buffer.tell() <= MAX_POST_IMAGE_SIZE:
            break
        quality -= 10

    filename = f'{uuid4().hex}.jpg'
    return ContentFile(buffer.getvalue(), name=filename)


def save_post_media(post, files):
    image_count = 0
    for uploaded_file in files:
        content_type = getattr(uploaded_file, 'content_type', '')
        if content_type in ALLOWED_POST_IMAGE_TYPES:
            if image_count >= MAX_POST_IMAGE_COUNT:
                continue
            image_count += 1
            file_to_save = uploaded_file
            if uploaded_file.size > MAX_POST_IMAGE_SIZE:
                file_to_save = compress_image(uploaded_file)
            PostMedia.objects.create(
                post=post,
                file=file_to_save,
                media_type=PostMedia.MEDIA_IMAGE,
            )
        elif content_type in ALLOWED_POST_VIDEO_TYPES and uploaded_file.size <= MAX_POST_VIDEO_SIZE:
            PostMedia.objects.create(
                post=post,
                file=uploaded_file,
                media_type=PostMedia.MEDIA_VIDEO,
            )


def home(request):
    ensure_default_taxonomy()
    profile = ensure_profile(request.user)
    selected_board = get_selected_board(request)
    selected_category = None if selected_board else get_selected_category(request)
    topic_category = selected_board.category if selected_board else selected_category
    chat_context = get_chat_context(request, selected_board, selected_category)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_board':
            category = get_object_or_404(Category, id=request.POST.get('category_id'))
            board_name = request.POST.get('board_name', '').strip()
            if board_name:
                board = get_or_create_routed_board(category, board_name)
                if board:
                    return redirect(f'/?board={board.slug}')
            return redirect('home')

        if action == 'send_chat':
            message = request.POST.get('message', '').strip()
            image = get_valid_chat_image(request)
            identity_mode = request.POST.get('identity_mode', ChatMessage.IDENTITY_ANONYMOUS)
            chat_scope = request.POST.get('chat_scope', chat_context['chat_scope'])
            private_user = None
            if identity_mode == ChatMessage.IDENTITY_REAL and not request.user.is_authenticated:
                identity_mode = ChatMessage.IDENTITY_ANONYMOUS
            if chat_scope == 'private':
                if not request.user.is_authenticated:
                    return redirect('login')
                private_user = User.objects.filter(id=request.POST.get('recipient_id')).first()
                if not private_user or private_user == request.user:
                    return redirect('home')
            if message or image:
                ChatMessage.objects.create(
                    board=selected_board if chat_scope == 'board' else None,
                    category=selected_category if chat_scope == 'category' else None,
                    user=request.user if request.user.is_authenticated else None,
                    recipient=private_user,
                    identity_mode=identity_mode,
                    message=message,
                    image=image,
                )
            if chat_scope == 'private' and private_user:
                return redirect(f'/?chat=private&private_user={private_user.id}&focus_chat=1')
            if selected_board:
                return redirect(f'/?board={selected_board.slug}&focus_chat=1')
            if selected_category:
                return redirect(f'/?category={selected_category.id}&focus_chat=1')
            return redirect('/?focus_chat=1')

        if action == 'toggle_like':
            if not request.user.is_authenticated:
                return redirect('login')
            post = get_object_or_404(Post, id=request.POST.get('post_id'))
            like = PostLike.objects.filter(post=post, user=request.user).first()
            if like:
                like.delete()
            else:
                PostLike.objects.create(post=post, user=request.user)
            if selected_board:
                return redirect(f'/?board={selected_board.slug}&restore_scroll=1')
            if selected_category:
                return redirect(f'/?category={selected_category.id}&restore_scroll=1')
            return redirect('/?restore_scroll=1')

        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        board_id = request.POST.get('board_id')
        board = TopicBoard.objects.filter(id=board_id).first()
        if title and content:
            post = Post.objects.create(
                title=title,
                content=content,
                board=board,
                author=request.user if request.user.is_authenticated else None,
            )
            save_post_media(post, request.FILES.getlist('media'))
        if board:
            return redirect(f'/?board={board.slug}')
        return redirect('home')

    posts = Post.objects.select_related(
        'author',
        'author__profile',
        'board',
        'board__category',
        'board__category__parent',
        'board__category__parent__parent',
    ).prefetch_related('media').annotate(
        like_count=Count('likes', distinct=True),
        comment_count=Count('comments', distinct=True),
    ).order_by('-created_at')
    if selected_board:
        posts = posts.filter(board=selected_board)
    elif selected_category:
        posts = posts.filter(board__category_id__in=get_descendant_category_ids(selected_category))

    profiles = UserProfile.objects.select_related('user').annotate(
        post_count=Count('user__posts', distinct=True),
        subscriber_count=Count('user__subscribers', distinct=True),
    ).order_by('-subscriber_count', '-post_count', '-created_at')[:8]
    boards = TopicBoard.objects.select_related(
        'category',
        'category__parent',
        'category__parent__parent',
    ).order_by('-created_at')[:36]
    popular_boards = TopicBoard.objects.select_related(
        'category',
        'category__parent',
        'category__parent__parent',
    ).annotate(
        post_count=Count('posts', distinct=True),
        chat_count=Count('chat_messages', distinct=True),
    ).order_by('-post_count', '-chat_count', '-created_at')[:10]
    popular_posts = Post.objects.select_related(
        'author',
        'author__profile',
        'board',
        'board__category',
        'board__category__parent',
        'board__category__parent__parent',
    ).annotate(
        like_count=Count('likes', distinct=True),
        comment_count=Count('comments', distinct=True),
    ).order_by('-like_count', '-comment_count', '-created_at')[:10]
    liked_post_ids = set()
    if request.user.is_authenticated:
        liked_post_ids = set(PostLike.objects.filter(
            user=request.user,
            post__in=posts,
        ).values_list('post_id', flat=True))

    return render(request, 'home.html', {
        'category_tree': build_category_tree(),
        'board_search_category': get_other_category(),
        'posts': list(posts),
        'sample_posts': SAMPLE_POSTS if not posts.exists() else [],
        'selected_board': selected_board,
        'selected_category': selected_category,
        'topic_category': topic_category,
        'topic_cards': get_topic_cards(topic_category),
        'topic_back_category': get_topic_back_category(topic_category),
        'subtopic_items': get_subtopic_items(topic_category, selected_board),
        'board_count': TopicBoard.objects.count(),
        'chat_messages': chat_context['chat_messages'],
        'chat_scope': chat_context['chat_scope'],
        'private_user': chat_context['private_user'],
        'chat_title': chat_context['chat_title'],
        'profiles': profiles,
        'profile': profile,
        'boards': boards,
        'popular_boards': popular_boards,
        'popular_posts': popular_posts,
        'liked_post_ids': liked_post_ids,
    })


def profile_feed(request, username):
    ensure_default_taxonomy()
    user = get_object_or_404(User, username=username)
    profile = ensure_profile(user)
    current_profile = ensure_profile(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_board':
            category = get_object_or_404(Category, id=request.POST.get('category_id'))
            board_name = request.POST.get('board_name', '').strip()
            if board_name:
                board = get_or_create_routed_board(category, board_name)
                if board:
                    return redirect(f'/?board={board.slug}')
            return redirect('profile_feed', username=user.username)

        if action == 'send_chat':
            message = request.POST.get('message', '').strip()
            image = get_valid_chat_image(request)
            identity_mode = request.POST.get('identity_mode', ChatMessage.IDENTITY_ANONYMOUS)
            private_user = None
            if request.POST.get('chat_scope') == 'private':
                if not request.user.is_authenticated:
                    return redirect('login')
                private_user = User.objects.filter(id=request.POST.get('recipient_id')).first()
                if not private_user or private_user == request.user:
                    return redirect('profile_feed', username=user.username)
            if identity_mode == ChatMessage.IDENTITY_REAL and not request.user.is_authenticated:
                identity_mode = ChatMessage.IDENTITY_ANONYMOUS
            if message or image:
                ChatMessage.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    recipient=private_user,
                    identity_mode=identity_mode,
                    message=message,
                    image=image,
                )
            if private_user:
                return redirect(f'/u/{user.username}/?chat=private&private_user={private_user.id}&focus_chat=1')
            return redirect(f'/u/{user.username}/?focus_chat=1')

        if action == 'toggle_subscription':
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user != user:
                subscription = Subscription.objects.filter(
                    subscriber=request.user,
                    target=user,
                ).first()
                if subscription:
                    subscription.delete()
                else:
                    Subscription.objects.create(subscriber=request.user, target=user)
            return redirect('profile_feed', username=user.username)

        if action == 'update_profile' and request.user == user:
            if 'display_name' in request.POST:
                profile.display_name = request.POST.get('display_name', '').strip() or user.username
            if 'bio' in request.POST:
                profile.bio = request.POST.get('bio', '').strip()[:160]
            photo = get_valid_profile_photo(request)
            if photo:
                profile.photo = photo
            profile.save()
            return redirect('profile_feed', username=user.username)

    if request.method == 'POST' and request.user == user:
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        if title and content:
            post = Post.objects.create(title=title, content=content, author=user)
            save_post_media(post, request.FILES.getlist('media'))
        return redirect('profile_feed', username=user.username)

    posts = Post.objects.select_related(
        'board',
        'board__category',
        'board__category__parent',
    ).prefetch_related('media').filter(author=user).order_by('-created_at')
    subscriber_sort = request.GET.get('subscriber_sort', 'date_desc')
    subscriber_ordering = {
        'name': ('subscriber__username', 'subscriber__profile__display_name'),
        'date_asc': ('created_at',),
        'posts': ('-subscriber_post_count', 'subscriber__username'),
        'date_desc': ('-created_at',),
    }
    if subscriber_sort not in subscriber_ordering:
        subscriber_sort = 'date_desc'
    subscribers = Subscription.objects.filter(target=user).select_related(
        'subscriber',
        'subscriber__profile',
    ).annotate(
        subscriber_post_count=Count('subscriber__posts', distinct=True),
    ).order_by(*subscriber_ordering[subscriber_sort])
    is_subscribed = False
    if request.user.is_authenticated and request.user != user:
        is_subscribed = Subscription.objects.filter(
            subscriber=request.user,
            target=user,
        ).exists()
    chat_context = get_chat_context(request)
    profiles = UserProfile.objects.select_related('user').order_by('-created_at')[:8]
    popular_boards = TopicBoard.objects.select_related(
        'category',
        'category__parent',
    ).annotate(
        post_count=Count('posts', distinct=True),
        chat_count=Count('chat_messages', distinct=True),
    ).order_by('-post_count', '-chat_count', '-created_at')[:10]
    return render(request, 'profile.html', {
        'feed_user': user,
        'feed_profile': profile,
        'profile': current_profile,
        'posts': posts,
        'is_subscribed': is_subscribed,
        'subscriber_count': user.subscribers.count(),
        'subscribers': subscribers,
        'subscriber_sort': subscriber_sort,
        'category_tree': build_category_tree(),
        'board_search_category': get_other_category(),
        'board_count': TopicBoard.objects.count(),
        'chat_messages': chat_context['chat_messages'],
        'chat_scope': chat_context['chat_scope'],
        'private_user': chat_context['private_user'],
        'chat_title': chat_context['chat_title'],
        'profiles': profiles,
        'popular_boards': popular_boards,
    })


def post_detail(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related(
            'author',
            'author__profile',
            'board',
            'board__category',
            'board__category__parent',
        ).prefetch_related('media'),
        id=post_id,
    )
    can_delete_post = (
        request.user.is_authenticated and
        request.user.username.casefold() == 'woobro7'
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_post':
            if not can_delete_post:
                return redirect('post_detail', post_id=post.id)
            board_slug = post.board.slug if post.board else None
            author_username = post.author.username if post.author else None
            post.delete()
            if board_slug:
                return redirect(f'/?board={board_slug}')
            if author_username:
                return redirect('profile_feed', username=author_username)
            return redirect('home')

        if action == 'toggle_like':
            if not request.user.is_authenticated:
                return redirect('login')
            like = PostLike.objects.filter(post=post, user=request.user).first()
            if like:
                like.delete()
            else:
                PostLike.objects.create(post=post, user=request.user)
            return redirect('post_detail', post_id=post.id)

        if action == 'add_comment':
            content = request.POST.get('content', '').strip()
            if content:
                PostComment.objects.create(
                    post=post,
                    user=request.user if request.user.is_authenticated else None,
                    content=content[:500],
                )
            return redirect('post_detail', post_id=post.id)

    comments = post.comments.select_related('user', 'user__profile')
    user_liked = False
    if request.user.is_authenticated:
        user_liked = post.likes.filter(user=request.user).exists()
    return render(request, 'post_detail.html', {
        'post': post,
        'comments': comments,
        'like_count': post.likes.count(),
        'comment_count': comments.count(),
        'user_liked': user_liked,
        'can_delete_post': can_delete_post,
    })


@login_required
def create(request):
    ensure_default_taxonomy()
    ensure_profile(request.user)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        board = TopicBoard.objects.filter(id=request.POST.get('board_id')).first()
        if not title or not content:
            return render(request, 'create.html', {'boards': TopicBoard.objects.all()})
        post = Post.objects.create(title=title, content=content, board=board, author=request.user)
        save_post_media(post, request.FILES.getlist('media'))
        if board:
            return redirect(f'/?board={board.slug}')
        return redirect('home')
    return render(request, 'create.html', {'boards': TopicBoard.objects.all()})


def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if username and password:
            user = User.objects.create_user(username=username, password=password)
            UserProfile.objects.create(user=user, display_name=username)
            return redirect('login')
    return render(request, 'signup.html')
