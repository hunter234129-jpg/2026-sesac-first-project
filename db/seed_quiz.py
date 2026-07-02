"""공부 로드맵 단원별 확인 문제(1문제씩) 시드 데이터를 config.py의 DB 접속 정보로 채우는 1회용 스크립트.
curriculum_topics가 먼저 시드되어 있어야 한다(db/seed_curriculum.py 먼저 실행).
실행: venv\\Scripts\\python.exe db\\seed_quiz.py
재실행해도 안전합니다(ON DUPLICATE KEY UPDATE로 내용만 갱신).
"""
import os
import sys
import json
import pymysql

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG

# key = curriculum_topics.id (db/seed_curriculum.py 시드 후 부여되는 값과 동일해야 함)
QUIZ = {
    116: {"question": "듣기·말하기 상황에서 상대방의 말을 들을 때 가장 바람직한 태도는?", "choices": ["상대방의 말이 끝나기 전에 반박을 준비한다", "표정은 무시하고 내용만 기계적으로 받아 적는다", "상대방의 말에 집중하며 공감적으로 반응한다", "관심 없는 주제면 듣기를 중단한다"], "answer_index": 2, "explanation": "경청은 상대의 말과 감정에 집중해 공감하며 반응하는 태도이다."},
    117: {"question": "시에서 소리의 규칙적인 반복으로 생기는 음악적 요소를 무엇이라 하는가?", "choices": ["운율", "심상", "반어", "역설"], "answer_index": 0, "explanation": "소리의 규칙적 반복으로 생기는 음악적 느낌을 운율이라 한다."},
    118: {"question": "소설을 구성하는 3요소로 알맞은 것은?", "choices": ["발단, 전개, 결말", "주제, 문체, 어조", "운율, 심상, 어조", "인물, 사건, 배경"], "answer_index": 3, "explanation": "소설은 인물, 사건, 배경을 3요소로 하여 이야기를 구성한다."},
    119: {"question": "설명하는 글의 특성으로 가장 적절한 것은?", "choices": ["글쓴이의 주장을 설득하기 위해 쓴다", "정보를 정확하고 객관적으로 전달한다", "상상으로 꾸며낸 이야기를 담는다", "개인적인 느낌과 정서를 표현한다"], "answer_index": 1, "explanation": "설명하는 글은 정보를 객관적이고 정확하게 전달하는 것이 목적이다."},
    120: {"question": "주장하는 글의 근거가 타당한지 판단하는 기준으로 가장 적절한 것은?", "choices": ["문장의 길이가 긴가", "표현이 화려한가", "근거가 주장을 논리적으로 뒷받침하는가", "글쓴이의 나이가 많은가"], "answer_index": 2, "explanation": "타당한 근거는 주장을 논리적으로 뒷받침할 수 있어야 한다."},
    121: {"question": "다음 중 사물의 이름을 나타내는 품사는?", "choices": ["동사", "명사", "부사", "조사"], "answer_index": 1, "explanation": "명사는 사람이나 사물의 이름을 나타내는 품사이다."},
    122: {"question": "문장에서 '무엇이 어찌하다'의 '어찌하다'에 해당하는 문장 성분은?", "choices": ["서술어", "주어", "목적어", "관형어"], "answer_index": 0, "explanation": "'어찌하다'에 해당하는 문장 성분은 서술어이다."},
    123: {"question": "훈민정음 자음 기본자의 제자 원리로 옳은 것은?", "choices": ["천, 지, 인 삼재를 본떠 만들었다", "기존 한자의 획을 그대로 가져왔다", "알파벳의 형태를 응용해 만들었다", "발음 기관의 모양을 본떠 만들었다"], "answer_index": 3, "explanation": "자음 기본자는 발음 기관의 모양을 본떠 만들었다."},
    124: {"question": "수필의 특성으로 가장 적절한 것은?", "choices": ["상연을 목적으로 대사와 지문으로 구성된다", "글쓴이의 개인적 경험과 생각을 자유로운 형식으로 표현한다", "운율이 있는 함축적 언어로 표현한다", "허구의 인물과 사건을 꾸며 낸 이야기이다"], "answer_index": 1, "explanation": "수필은 글쓴이의 경험과 생각을 자유로운 형식으로 담은 글이다."},
    125: {"question": "논설문에서 주장을 뒷받침하기 위해 제시하는 자료나 이유를 무엇이라 하는가?", "choices": ["배경", "심상", "운율", "근거"], "answer_index": 3, "explanation": "주장을 뒷받침하는 자료나 이유를 근거라고 한다."},
    126: {"question": "두 대상의 공통점과 차이점을 견주어 설명하는 방법은?", "choices": ["정의", "예시", "비교·대조", "분류"], "answer_index": 2, "explanation": "공통점과 차이점을 견주어 설명하는 방법은 비교·대조이다."},
    127: {"question": "'풋사과'처럼 어근에 접사가 붙어 만들어진 단어를 무엇이라 하는가?", "choices": ["파생어", "합성어", "단일어", "어절"], "answer_index": 0, "explanation": "'풋-'과 같은 접사가 어근에 붙은 단어를 파생어라 한다."},
    128: {"question": "주어와 서술어의 관계가 두 번 이상 나타나는 문장을 무엇이라 하는가?", "choices": ["홑문장", "겹문장", "단문", "명사절"], "answer_index": 1, "explanation": "주어와 서술어 관계가 두 번 이상 나타나면 겹문장이다."},
    129: {"question": "말하는 이와 듣는 이가 처한 시간, 장소 등 담화 이해에 영향을 주는 배경을 무엇이라 하는가?", "choices": ["상황 맥락", "어조", "문체", "운율"], "answer_index": 0, "explanation": "담화 이해에 영향을 주는 시간, 장소 등의 배경을 상황 맥락이라 한다."},
    130: {"question": "인쇄 매체와 비교할 때 영상 매체가 지닌 특성으로 가장 적절한 것은?", "choices": ["문자로만 정보를 전달한다", "휴대와 보관이 간편한 종이 형태이다", "소리와 영상을 결합해 정보를 전달한다", "정보 전달이 느리고 일방적이다"], "answer_index": 2, "explanation": "영상 매체는 소리와 영상을 결합해 정보를 전달한다."},
    131: {"question": "조선 시대에 발달한 3장 6구 형식의 정형시는?", "choices": ["향가", "가사", "판소리", "시조"], "answer_index": 3, "explanation": "시조는 3장 6구 형식을 지닌 조선 시대의 정형시이다."},
    132: {"question": "시 속에서 시인을 대신하여 말하는 존재를 무엇이라 하는가?", "choices": ["시적 화자", "서술자", "방관자", "청자"], "answer_index": 0, "explanation": "시 속에서 시인을 대신해 말하는 존재를 시적 화자라 한다."},
    133: {"question": "서술자가 작품 밖에서 인물의 속마음까지 모두 아는 시점은?", "choices": ["1인칭 주인공 시점", "3인칭 관찰자 시점", "전지적 작가 시점", "1인칭 관찰자 시점"], "answer_index": 2, "explanation": "전지적 작가 시점은 서술자가 인물의 내면까지 모두 아는 시점이다."},
    134: {"question": "일반적 원리를 전제로 삼아 특수한 사실을 결론으로 이끌어 내는 논증 방법은?", "choices": ["귀납 논증", "연역 논증", "유추 논증", "변증 논증"], "answer_index": 1, "explanation": "일반적 원리에서 특수한 사실을 이끌어 내는 논증이 연역 논증이다."},
    135: {"question": "다음 중 한글 맞춤법에 맞게 표기된 것은?", "choices": ["몇일", "왠일", "뒤치닥거리", "오랜만"], "answer_index": 3, "explanation": "'오랜만'이 한글 맞춤법에 맞는 표기이다."},
    136: {"question": "문장과 문단이 접속어나 지시어로 긴밀하게 이어지는 글의 특성은?", "choices": ["통일성", "간결성", "명료성", "응집성"], "answer_index": 3, "explanation": "접속어나 지시어로 문장을 긴밀히 잇는 특성을 응집성이라 한다."},
    137: {"question": "토론에서 자신의 주장과 근거를 처음으로 제시하는 발언 단계는?", "choices": ["반론", "입론", "최종 발언", "협상"], "answer_index": 1, "explanation": "토론에서 주장과 근거를 처음 제시하는 단계는 입론이다."},
    138: {"question": "공동의 문제 해결을 위해 여러 사람이 협력적으로 의견을 나누는 말하기 방식은?", "choices": ["토의", "토론", "협상", "발표"], "answer_index": 0, "explanation": "협력적으로 문제 해결책을 찾는 말하기 방식은 토의이다."},
    139: {"question": "작문 과정에서 목적과 예상 독자를 고려해 쓸 내용을 마련하는 단계는?", "choices": ["고쳐쓰기", "초고 쓰기", "내용 생성하기", "편집하기"], "answer_index": 2, "explanation": "쓸 내용을 마련하는 작문 단계는 내용 생성하기이다."},
    140: {"question": "뜻을 가진 가장 작은 말의 단위를 무엇이라 하는가?", "choices": ["음운", "어절", "형태소", "음절"], "answer_index": 2, "explanation": "뜻을 가진 가장 작은 말의 단위는 형태소이다."},
    141: {"question": "필요한 정보를 빠르게 찾기 위해 글 전체를 훑어보며 읽는 방법은?", "choices": ["정독", "음독", "묵독", "훑어 읽기"], "answer_index": 3, "explanation": "필요한 부분만 빠르게 살펴 읽는 방법은 훑어 읽기이다."},
    142: {"question": "인물, 사건, 배경을 갖추고 서술자가 이야기를 전달하는 문학 갈래는?", "choices": ["서정", "서사", "극", "교술"], "answer_index": 1, "explanation": "인물, 사건, 배경을 갖춘 이야기 갈래는 서사이다."},
    143: {"question": "작품 속에서 작가가 전달하고자 하는 중심 생각을 무엇이라 하는가?", "choices": ["주제", "소재", "배경", "문체"], "answer_index": 0, "explanation": "작품에서 작가가 전달하려는 중심 생각은 주제이다."},
    144: {"question": "고려 시대에 평민들 사이에서 불린, 후렴구가 발달한 노래 갈래는?", "choices": ["고려가요", "향가", "시조", "가사"], "answer_index": 0, "explanation": "후렴구가 발달한 고려 시대 평민 노래는 고려가요이다."},
    145: {"question": "갑오개혁 이후 언문일치를 지향하며 등장한 근대적 소설을 무엇이라 하는가?", "choices": ["고전 소설", "판소리계 소설", "신소설", "계몽 가사"], "answer_index": 2, "explanation": "언문일치를 지향한 갑오개혁 이후의 근대 소설은 신소설이다."},
    146: {"question": "원관념 없이 보조 관념만으로 추상적 의미를 나타내는 표현 방법은?", "choices": ["직유", "은유", "반어", "상징"], "answer_index": 3, "explanation": "원관념 없이 보조 관념만 제시하는 표현법은 상징이다."},
    147: {"question": "서술자가 작품 속 주변 인물로 등장해 주인공을 관찰하며 서술하는 시점은?", "choices": ["1인칭 주인공 시점", "1인칭 관찰자 시점", "전지적 작가 시점", "3인칭 관찰자 시점"], "answer_index": 1, "explanation": "작품 속 인물이 주인공을 관찰해 서술하면 1인칭 관찰자 시점이다."},
    148: {"question": "희곡에서 인물의 동작, 표정, 무대 장치 등을 지시하는 부분을 무엇이라 하는가?", "choices": ["대사", "지문", "해설", "방백"], "answer_index": 1, "explanation": "인물의 동작이나 무대 지시를 나타내는 부분은 지문이다."},
    149: {"question": "글에 직접 드러나지 않은 내용을 맥락을 바탕으로 짐작하며 읽는 방법은?", "choices": ["추론적 읽기", "사실적 읽기", "비판적 읽기", "감상적 읽기"], "answer_index": 0, "explanation": "맥락을 바탕으로 숨은 내용을 짐작하며 읽는 것은 추론적 읽기이다."},
    150: {"question": "인문·예술 제재의 글을 읽을 때 가장 중점을 두어야 할 것은?", "choices": ["실험 결과의 수치만 암기한다", "등장인물의 대사를 모두 외운다", "핵심 개념어의 의미와 관계를 정확히 파악한다", "그림의 색감만 감상한다"], "answer_index": 2, "explanation": "인문·예술 지문은 핵심 개념어의 의미 파악이 가장 중요하다."},
    151: {"question": "사회·문화 제재 지문을 읽을 때 가장 중요한 독해 방법은?", "choices": ["통계 수치의 글꼴을 확인한다", "글쓴이의 출신 지역을 파악한다", "문장의 길이만 비교한다", "사회 현상의 원인과 다양한 관점의 논리를 파악한다"], "answer_index": 3, "explanation": "사회·문화 지문은 현상의 원인과 다양한 관점을 파악해야 한다."},
    152: {"question": "과학·기술 제재 지문을 읽을 때 가장 중요한 것은?", "choices": ["글의 분량이 얼마나 되는지 확인한다", "필자의 감정 표현을 찾는다", "비유적 표현의 운율을 분석한다", "대상의 원리와 과정을 단계별로 이해한다"], "answer_index": 3, "explanation": "과학·기술 지문은 원리와 과정을 단계별로 이해해야 한다."},
    153: {"question": "발표에서 다른 자료를 인용할 때 반드시 밝혀야 하는 것은?", "choices": ["발표자의 목소리 크기", "청중의 인원수", "자료의 출처", "발표 장소의 크기"], "answer_index": 2, "explanation": "자료를 인용할 때는 반드시 출처를 밝혀야 한다."},
    154: {"question": "문자, 음성, 이미지, 영상 등이 결합되어 정보를 전달하는 매체 언어의 특성은?", "choices": ["복합 양식성", "단일성", "폐쇄성", "고정성"], "answer_index": 0, "explanation": "여러 양식이 결합된 매체 언어의 특성을 복합 양식성이라 한다."},
    155: {"question": "'엄마가 아이에게 옷을 입혔다.'에 나타난 문법 표현은?", "choices": ["피동 표현", "사동 표현", "높임 표현", "부정 표현"], "answer_index": 1, "explanation": "'입히다'는 '입다'의 사동사가 쓰인 사동 표현이다."},
    156: {"question": "1인 미디어 방송이 텔레비전 방송과 다르게 갖는 소통 방식의 특징은?", "choices": ["시청자와 실시간 쌍방향 소통이 활발하다", "정해진 편성 시간표에 따라서만 송출된다", "대규모 방송 장비와 인력이 반드시 필요하다", "시청자 반응을 전혀 반영할 수 없다"], "answer_index": 0, "explanation": "1인 미디어는 실시간 쌍방향 소통이 활발하다는 특징이 있다."},
    157: {"question": "정보량이 많은 고난도 독서 지문을 읽을 때 가장 효과적인 전략은?", "choices": ["모든 문장을 그대로 암기한다", "문단별 핵심 정보를 정리하며 정보 간 관계를 구조화한다", "어려운 단어가 나오면 읽기를 중단한다", "마지막 문단만 읽고 전체를 판단한다"], "answer_index": 1, "explanation": "정보량이 많은 지문은 핵심 정보를 정리하며 구조화해 읽어야 한다."},
    158: {"question": "두 작품을 엮은 복합 지문을 감상할 때 가장 중요한 전략은?", "choices": ["두 작품을 완전히 분리하여 따로 이해한다", "먼저 나온 작품만 집중적으로 분석한다", "작품의 길이만 비교한다", "두 작품의 공통점과 차이점을 비교하며 연관성을 파악한다"], "answer_index": 3, "explanation": "복합 지문은 두 작품의 공통점과 차이점을 비교하며 읽어야 한다."},
    71: {"question": "She ___ to school every day. 빈칸에 알맞은 것은?", "choices": ["goes", "go", "is go", "going"], "answer_index": 0, "explanation": "주어가 3인칭 단수이므로 일반동사에 -es를 붙인 goes가 알맞다."},
    72: {"question": "Look! The dog ___ in the yard now. 빈칸에 알맞은 것은?", "choices": ["runs", "is running", "ran", "run"], "answer_index": 1, "explanation": "지금 진행 중인 동작은 현재진행형(is+동사원형-ing)으로 표현한다."},
    73: {"question": "I ___ my homework last night. 빈칸에 알맞은 것은?", "choices": ["do", "does", "did", "doing"], "answer_index": 2, "explanation": "last night은 과거를 나타내므로 do의 과거형 did가 알맞다."},
    74: {"question": "A: I've already decided. I ___ visit my grandmother this weekend. 빈칸에 알맞은 것은?", "choices": ["will", "is", "will be", "am going to"], "answer_index": 3, "explanation": "이미 계획한 일이므로 be going to(am going to)가 알맞다."},
    75: {"question": "Fish ___ live without water. 빈칸에 알맞은 것은?", "choices": ["cannot", "must not", "may not", "should not"], "answer_index": 0, "explanation": "물 없이 살 수 없다는 능력의 부정은 cannot으로 표현한다."},
    76: {"question": "I saw ___ elephant at the zoo yesterday. 빈칸에 알맞은 것은?", "choices": ["a", "an", "the", "some"], "answer_index": 1, "explanation": "elephant는 모음 발음으로 시작하는 단수 가산명사이므로 an을 쓴다."},
    77: {"question": "These are Mike's shoes. ___ are new. 빈칸에 알맞은 것은?", "choices": ["He", "Him", "His", "Himself"], "answer_index": 2, "explanation": "Mike의 소유를 나타내는 소유대명사 His가 주어 자리에 알맞다."},
    78: {"question": "She sings ___. (그녀는 아름답게 노래한다) 빈칸에 알맞은 것은?", "choices": ["beautiful", "beauty", "more beautiful", "beautifully"], "answer_index": 3, "explanation": "동사 sings를 수식하므로 부사 beautifully가 알맞다."},
    79: {"question": "Mt. Everest is ___ mountain in the world. 빈칸에 알맞은 것은?", "choices": ["the highest", "higher", "the higher", "more high"], "answer_index": 0, "explanation": "셋 이상 중 가장 높다는 의미이므로 최상급 the highest가 알맞다."},
    80: {"question": "A: ___ she like coffee? B: Yes, she does. 빈칸에 알맞은 것은?", "choices": ["Do", "Does", "Is", "Did"], "answer_index": 1, "explanation": "일반동사 현재형 의문문에서 주어가 3인칭 단수이면 Does를 쓴다."},
    81: {"question": "I have never ___ a panda before. 빈칸에 알맞은 것은?", "choices": ["see", "saw", "seen", "seeing"], "answer_index": 2, "explanation": "현재완료(have+과거분사)이므로 see의 과거분사 seen이 알맞다."},
    82: {"question": "She decided ___ abroad to study English. 빈칸에 알맞은 것은?", "choices": ["go", "going", "went", "to go"], "answer_index": 3, "explanation": "decide는 목적어로 to부정사를 취하는 동사이다."},
    83: {"question": "___ vegetables is good for your health. 빈칸에 알맞은 것은?", "choices": ["Eating", "Eat", "To eating", "Ate"], "answer_index": 0, "explanation": "문장의 주어 자리이므로 동명사 Eating이 알맞다."},
    84: {"question": "The movie was so ___ that I fell asleep. 빈칸에 알맞은 것은?", "choices": ["bored", "boring", "bore", "to bore"], "answer_index": 1, "explanation": "영화가 지루한 감정을 유발하므로 현재분사 boring이 알맞다."},
    85: {"question": "I stayed home ___ it was raining. 빈칸에 알맞은 것은?", "choices": ["but", "so", "because", "or"], "answer_index": 2, "explanation": "비가 와서 집에 있었다는 이유를 나타내는 because가 알맞다."},
    86: {"question": "The man ___ is standing there is my uncle. 빈칸에 알맞은 것은?", "choices": ["which", "whose", "what", "who"], "answer_index": 3, "explanation": "사람을 선행사로 받는 주격 관계대명사 who가 알맞다."},
    87: {"question": "The window ___ by the boy yesterday. 빈칸에 알맞은 것은?", "choices": ["was broken", "broke", "is broken", "broken"], "answer_index": 0, "explanation": "창문이 소년에 의해 깨진 것이므로 수동태 과거형 was broken이 알맞다."},
    88: {"question": "If it rains tomorrow, we ___ the picnic. 빈칸에 알맞은 것은?", "choices": ["cancel", "will cancel", "canceled", "would cancel"], "answer_index": 1, "explanation": "조건절이 현재형이면 주절은 will+동사원형을 쓴다."},
    89: {"question": "다음 문장은 몇 형식 문장인가? 'She made me happy.'", "choices": ["3형식", "4형식", "5형식", "2형식"], "answer_index": 2, "explanation": "목적어(me)와 목적격보어(happy)가 있으므로 5형식 문장이다."},
    90: {"question": "My brother, ___ lives in Seoul, is a doctor. 빈칸에 알맞은 것은?", "choices": ["that", "which", "whom", "who"], "answer_index": 3, "explanation": "콤마로 구분된 계속적 용법에는 that을 쓸 수 없고 who를 쓴다."},
    91: {"question": "This is the town ___ I was born. 빈칸에 알맞은 것은?", "choices": ["where", "which", "when", "why"], "answer_index": 0, "explanation": "장소를 나타내는 선행사 town 뒤에는 관계부사 where가 알맞다."},
    92: {"question": "If I ___ a bird, I would fly to you. 빈칸에 알맞은 것은?", "choices": ["am", "were", "was", "will be"], "answer_index": 1, "explanation": "가정법 과거에서 be동사는 인칭에 관계없이 were를 쓴다."},
    93: {"question": "다음 문장을 분사구문으로 바르게 바꾼 것은? 'As she didn't know what to do, she asked for help.'", "choices": ["Knowing not what to do, she asked for help.", "Not know what to do, she asked for help.", "Not knowing what to do, she asked for help.", "Didn't knowing what to do, she asked for help."], "answer_index": 2, "explanation": "부사절의 부정은 분사 앞에 Not을 붙여 Not knowing으로 바꾼다."},
    94: {"question": "직접화법을 간접화법으로 바르게 바꾼 것은? He said, 'I am tired.'", "choices": ["He said that he is tired.", "He said that I was tired.", "He says that he was tired.", "He said that he was tired."], "answer_index": 3, "explanation": "전달동사가 과거이므로 am은 was로, I는 he로 바뀐다."},
    95: {"question": "다음 빈칸에 알맞은 것은? Never ___ such a beautiful sunset.", "choices": ["have I seen", "I have seen", "I saw", "did I saw"], "answer_index": 0, "explanation": "부정어 Never가 문두에 오면 주어와 조동사가 도치된다."},
    96: {"question": "다음 글의 흐름상 빈칸에 들어갈 연결어로 가장 적절한 것은? Tom practiced the piano every day for a year. ___, he still made mistakes during the concert.", "choices": ["Therefore", "However", "For example", "In addition"], "answer_index": 1, "explanation": "앞뒤 내용이 상반되므로 역접의 연결어 However가 알맞다."},
    97: {"question": "다음 문장 전체의 주어(S)로 알맞은 것은? 'The book that I bought yesterday at the store near my house was very interesting.'", "choices": ["I", "The store", "The book", "My house"], "answer_index": 2, "explanation": "that절은 The book을 수식하는 관계절이므로 문장의 주어는 The book이다."},
    98: {"question": "I remember ___ him at the party last year. 빈칸에 알맞은 것은?", "choices": ["to meet", "meet", "met", "meeting"], "answer_index": 3, "explanation": "과거에 만난 일을 기억한다는 의미이므로 remember 뒤에 동명사 meeting이 알맞다."},
    99: {"question": "This is the reason ___ she was late. 빈칸에 알맞은 것은?", "choices": ["why", "which", "when", "where"], "answer_index": 0, "explanation": "이유를 나타내는 선행사 reason 뒤에는 관계부사 why가 알맞다."},
    100: {"question": "다음 중 '주장하는 글(논설문)'을 읽을 때 가장 먼저 파악해야 할 것은?", "choices": ["등장인물의 이름", "글쓴이의 주장(요지)", "문장의 개수", "사용된 전치사의 종류"], "answer_index": 1, "explanation": "논설문은 글쓴이의 주장과 근거를 파악하는 것이 핵심이다."},
    101: {"question": "다음 글의 요지로 가장 적절한 것은? Reading books regularly improves vocabulary, critical thinking, and focus. Everyone should make time to read every day.", "choices": ["독서는 시간 낭비이다", "어휘력은 타고나는 것이다", "매일 독서하는 습관은 유익하다", "집중력은 운동으로만 길러진다"], "answer_index": 2, "explanation": "글은 매일 독서하는 것이 여러 면에서 유익하다고 말하고 있다."},
    102: {"question": "다음 빈칸에 들어갈 말로 가장 적절한 것은? Bears, for example, ___ for several months to save energy when food is scarce in winter.", "choices": ["migrate", "hunt", "communicate", "hibernate"], "answer_index": 3, "explanation": "곰이 겨울에 에너지를 아끼기 위해 하는 행동은 동면(hibernate)이다."},
    103: {"question": "다음 문장 뒤에 이어질 순서로 가장 적절한 것은? 'Many people think exercise is only about losing weight.' (A) In fact, it also improves mental health and sleep. (B) For example, it reduces stress and anxiety. (C) However, that is not the whole story.", "choices": ["(C)-(A)-(B)", "(A)-(B)-(C)", "(B)-(C)-(A)", "(A)-(C)-(B)"], "answer_index": 0, "explanation": "역접(C) 후 부연설명(A)과 구체적 예시(B) 순서가 논리적으로 자연스럽다."},
    104: {"question": "다음 중 어법상 틀린 문장은?", "choices": ["She has lived here since 2010.", "He don't like coffee.", "They are playing soccer now.", "I have never been to Paris."], "answer_index": 1, "explanation": "주어가 He이므로 don't가 아니라 doesn't를 써야 한다."},
    105: {"question": "다음 밑줄 친 표현이 의미하는 바로 가장 적절한 것은? After failing three times, Mia finally passed. She said, 'The darkest hour is just before the dawn.'", "choices": ["어둠은 영원히 지속된다", "시험은 아침에 봐야 한다", "가장 힘든 순간 뒤에 좋은 일이 온다", "밤에는 공부하지 말아야 한다"], "answer_index": 2, "explanation": "이 표현은 힘든 시기 뒤에 희망적인 상황이 온다는 뜻이다."},
    106: {"question": "다음 글에 나타난 'she'의 심경으로 가장 적절한 것은? Her hands were shaking as she opened the envelope. When she read 'Accepted,' tears filled her eyes and she smiled.", "choices": ["지루함", "분노", "무관심", "감격과 기쁨"], "answer_index": 3, "explanation": "합격 소식에 눈물을 흘리며 웃는 모습은 감격과 기쁨을 나타낸다."},
    107: {"question": "다음 글의 요약문 빈칸에 가장 적절한 것은? Plastic waste is harming ocean life, so many countries are now banning single-use plastics. → Countries are banning ___ to protect the ocean.", "choices": ["single-use plastics", "fossil fuels", "plastic recycling", "fishing nets"], "answer_index": 0, "explanation": "본문에서 국가들이 금지하는 대상은 일회용 플라스틱이다."},
    108: {"question": "다음 글의 내용과 일치하는 것은? Jake moved to a new city and felt lonely at first. However, he joined a local soccer club, and now he has many friends.", "choices": ["Jake는 이사 후에도 계속 외로웠다", "Jake는 축구 동아리에 가입해 친구를 사귀었다", "Jake는 이사하지 않았다", "Jake는 친구가 없다"], "answer_index": 1, "explanation": "Jake는 축구 동아리에 가입한 후 많은 친구를 사귀었다고 나와 있다."},
    109: {"question": "다음 안내문의 내용과 일치하지 않는 것은? [Library Notice] Open Mon-Fri, 9 AM-6 PM. Closed on weekends and holidays. Membership card required to borrow books.", "choices": ["도서관은 평일 오전 9시에 문을 연다", "공휴일에는 휴관한다", "회원증 없이도 책을 빌릴 수 있다", "주말에는 운영하지 않는다"], "answer_index": 2, "explanation": "안내문에 따르면 책을 빌리려면 회원증이 필요하다."},
    110: {"question": "다음 우리말을 영어로 가장 바르게 옮긴 것은? '나는 어제 그녀에게 편지를 썼다.'", "choices": ["I write her a letter yesterday.", "I have written her a letter yesterday.", "I wrote to she a letter yesterday.", "I wrote a letter to her yesterday."], "answer_index": 3, "explanation": "과거 시점(yesterday)에 맞춰 wrote를 쓰고 to her로 대상을 나타낸다."},
    111: {"question": "다음 빈칸에 들어갈 말로 가장 적절한 것은? Success is often attributed to talent, but research shows that many experts argue that ___ is the true predictor of achievement, not innate ability.", "choices": ["deliberate practice", "luck", "physical strength", "family background"], "answer_index": 0, "explanation": "글 전체가 재능보다 꾸준한 연습(deliberate practice)의 중요성을 강조하고 있다."},
    112: {"question": "다음 빈칸에 문맥상 가장 적절한 단어는? The company's profits have significantly ___ over the past year due to poor management.", "choices": ["increased", "declined", "improved", "soared"], "answer_index": 1, "explanation": "경영 부실로 인한 결과이므로 이익이 감소했다(declined)는 의미가 적절하다."},
    113: {"question": "다음 글에 나타난 필자의 태도로 가장 적절한 것은? Urban farming helps provide fresh produce, but critics say its yield is too small. Nevertheless, supporters believe its benefits outweigh its limitations.", "choices": ["도시 농업을 전면 부정한다", "도시 농업이 식량 문제를 완전히 해결한다고 주장한다", "도시 농업의 한계와 장점을 균형 있게 제시한다", "도시 농업과 무관한 내용을 다룬다"], "answer_index": 2, "explanation": "필자는 도시 농업의 한계와 장점을 함께 균형 있게 제시하고 있다."},
    114: {"question": "다음 글을 한 문장으로 요약할 때 가장 적절한 것은? Sleep deprivation affects memory, mood, and decision-making. Adults who sleep less than six hours perform worse on cognitive tasks.", "choices": ["수면 부족은 신체 건강에만 영향을 미친다", "수면은 기억력과 무관하다", "성인은 하루 3시간만 자도 충분하다", "충분한 수면은 인지 기능에 중요하다"], "answer_index": 3, "explanation": "수면 부족이 인지 기능 저하로 이어진다는 내용을 요약한 것이다."},
    115: {"question": "다음 중 논설문(에세이)의 서론에 들어갈 내용으로 가장 적절한 것은?", "choices": ["주제 제시 및 글쓴이의 주장", "결론 재진술", "세부 근거 3가지 나열", "참고문헌 목록"], "answer_index": 0, "explanation": "서론에서는 글의 주제와 글쓴이의 주장을 제시하는 것이 일반적이다."},
    1: {"question": "84를 소인수분해하면?", "choices": ["2²×3×7", "2×3²×7", "2²×3×5", "2×3×7²"], "answer_index": 0, "explanation": "84=2×2×3×7이므로 2²×3×7이다."},
    2: {"question": "12와 18의 최대공약수와 최소공배수를 순서대로 구하면?", "choices": ["3, 36", "6, 36", "6, 72", "2, 108"], "answer_index": 1, "explanation": "12=2²×3, 18=2×3²이므로 최대공약수 6, 최소공배수 36이다."},
    3: {"question": "수직선 위에서 -3과 2 사이의 거리는?", "choices": ["6", "-5", "5", "1"], "answer_index": 2, "explanation": "두 수 사이의 거리는 |2-(-3)|=5이다."},
    4: {"question": "(-2)+5×(-3)을 계산하면?", "choices": ["17", "-21", "13", "-17"], "answer_index": 3, "explanation": "곱셈을 먼저 계산하면 5×(-3)=-15, -2+(-15)=-17이다."},
    5: {"question": "x=3일 때, 2x+1의 값은?", "choices": ["6", "7", "8", "9"], "answer_index": 0, "explanation": "2×3+1=7이다."},
    6: {"question": "일차방정식 3x-5=7을 풀면?", "choices": ["3", "4", "5", "-4"], "answer_index": 1, "explanation": "3x=12이므로 x=4이다."},
    7: {"question": "점 (2, -3)은 좌표평면의 어느 사분면 위에 있는가?", "choices": ["제1사분면", "제2사분면", "제4사분면", "제3사분면"], "answer_index": 2, "explanation": "x좌표가 양수, y좌표가 음수이면 제4사분면이다."},
    8: {"question": "두 직선이 서로 수직으로 만날 때 이루는 각의 크기는?", "choices": ["180°", "60°", "45°", "90°"], "answer_index": 3, "explanation": "수직으로 만나면 두 직선이 이루는 각은 90°이다."},
    9: {"question": "다음 중 삼각형의 합동 조건이 아닌 것은?", "choices": ["AAA(세 각이 각각 같다)", "SSS(세 변이 각각 같다)", "SAS(두 변과 그 끼인각이 각각 같다)", "ASA(한 변과 그 양 끝 각이 각각 같다)"], "answer_index": 0, "explanation": "세 각이 같은 것은 합동이 아니라 닮음 조건이다."},
    10: {"question": "정오각형의 한 내각의 크기는?", "choices": ["100°", "108°", "120°", "90°"], "answer_index": 1, "explanation": "내각의 합은 (5-2)×180°=540°이므로 한 내각은 108°이다."},
    11: {"question": "한 모서리의 길이가 3인 정육면체의 부피는?", "choices": ["9", "18", "27", "36"], "answer_index": 2, "explanation": "정육면체의 부피는 3³=27이다."},
    12: {"question": "도수분포표에서 모든 계급의 도수를 더한 값은 무엇과 같은가?", "choices": ["계급값의 합", "계급의 개수", "평균", "전체 도수(변량의 총 개수)"], "answer_index": 3, "explanation": "각 계급의 도수를 모두 더하면 전체 자료의 개수인 전체 도수가 된다."},
    13: {"question": "순환소수 0.777…을 기약분수로 나타내면?", "choices": ["7/9", "7/10", "7/99", "77/100"], "answer_index": 0, "explanation": "x=0.777…이면 10x-x=7이므로 x=7/9이다."},
    14: {"question": "2a³ × 3a²을 계산하면?", "choices": ["5a⁵", "6a⁵", "6a⁶", "5a⁶"], "answer_index": 1, "explanation": "계수는 2×3=6, 지수는 3+2=5이므로 6a⁵이다."},
    15: {"question": "(2x+3)+(x-1)을 계산하면?", "choices": ["3x+4", "x+2", "3x+2", "3x-2"], "answer_index": 2, "explanation": "동류항끼리 더하면 3x+2이다."},
    16: {"question": "부등식 2x-3>5를 풀면?", "choices": ["x<4", "x>1", "x<1", "x>4"], "answer_index": 3, "explanation": "2x>8이므로 x>4이다."},
    17: {"question": "연립방정식 x+y=5, x-y=1의 해는?", "choices": ["x=3, y=2", "x=2, y=3", "x=4, y=1", "x=1, y=4"], "answer_index": 0, "explanation": "두 식을 더하면 2x=6, x=3이고 y=2이다."},
    18: {"question": "일차함수 y=2x-1의 기울기는?", "choices": ["-1", "2", "1", "-2"], "answer_index": 1, "explanation": "y=ax+b에서 기울기는 a이므로 2이다."},
    19: {"question": "일차방정식 x-y=2와 x+y=4의 그래프의 교점 좌표는?", "choices": ["(1, 3)", "(2, 2)", "(3, 1)", "(4, 0)"], "answer_index": 2, "explanation": "두 식을 더하면 x=3, 빼면 y=1이다."},
    20: {"question": "동전 한 개를 두 번 던질 때 모두 앞면이 나올 확률은?", "choices": ["1/2", "1/3", "2/3", "1/4"], "answer_index": 3, "explanation": "앞면이 나올 확률 1/2를 두 번 곱하면 1/4이다."},
    21: {"question": "이등변삼각형의 꼭지각이 40°일 때 한 밑각의 크기는?", "choices": ["70°", "80°", "60°", "50°"], "answer_index": 0, "explanation": "밑각은 (180°-40°)÷2=70°이다."},
    22: {"question": "평행사변형에서 두 대각선은 서로 어떤 관계에 있는가?", "choices": ["수직이등분한다", "이등분한다", "삼등분한다", "합동이 되게 한다"], "answer_index": 1, "explanation": "평행사변형의 두 대각선은 서로를 이등분한다."},
    23: {"question": "닮음비가 2:3인 두 삼각형에서 작은 삼각형의 한 변이 4일 때 대응하는 큰 삼각형의 변의 길이는?", "choices": ["8", "5", "6", "9"], "answer_index": 2, "explanation": "4×(3/2)=6이다."},
    24: {"question": "직각을 낀 두 변의 길이가 6, 8인 직각삼각형의 빗변의 길이는?", "choices": ["14", "12", "√48", "10"], "answer_index": 3, "explanation": "피타고라스 정리에 의해 √(6²+8²)=√100=10이다."},
    25: {"question": "√16의 값은?", "choices": ["4", "8", "±4", "2"], "answer_index": 0, "explanation": "√16은 16의 양의 제곱근인 4를 나타낸다."},
    26: {"question": "√2 × √8을 계산하면?", "choices": ["√10", "4", "2√10", "16"], "answer_index": 1, "explanation": "√2×√8=√16=4이다."},
    27: {"question": "(x+3)(x-3)을 전개하면?", "choices": ["x²+9", "x²+6x-9", "x²-9", "x²-6x-9"], "answer_index": 2, "explanation": "합차 공식에 의해 x²-9이다."},
    28: {"question": "x²-5x+6을 인수분해하면?", "choices": ["(x-1)(x-6)", "(x+2)(x+3)", "(x-6)(x+1)", "(x-2)(x-3)"], "answer_index": 3, "explanation": "곱이 6, 합이 -5인 두 수는 -2, -3이다."},
    29: {"question": "이차방정식 x²-3x-4=0의 해는?", "choices": ["x=4 또는 x=-1", "x=-4 또는 x=1", "x=2 또는 x=-2", "x=1 또는 x=4"], "answer_index": 0, "explanation": "(x-4)(x+1)=0이므로 x=4 또는 x=-1이다."},
    30: {"question": "이차함수 y=x²-4x+3의 그래프의 꼭짓점의 x좌표는?", "choices": ["4", "2", "-2", "1"], "answer_index": 1, "explanation": "x=-b/2a=4/2=2이다."},
    31: {"question": "직각삼각형에서 한 예각이 30°일 때 sin30°의 값은?", "choices": ["√3/2", "√2/2", "1/2", "1"], "answer_index": 2, "explanation": "30°의 사인값은 1/2이다."},
    32: {"question": "원의 접선은 접점에서 그은 반지름과 어떤 관계에 있는가?", "choices": ["평행하다", "일치한다", "60°를 이룬다", "수직이다"], "answer_index": 3, "explanation": "원의 접선은 접점에서의 반지름과 수직이다."},
    33: {"question": "한 호에 대한 원주각의 크기가 35°일 때 그 호에 대한 중심각의 크기는?", "choices": ["70°", "35°", "17.5°", "105°"], "answer_index": 0, "explanation": "중심각은 원주각의 2배이므로 70°이다."},
    34: {"question": "자료 2, 4, 6, 8, 10의 평균은?", "choices": ["5", "6", "7", "8"], "answer_index": 1, "explanation": "합 30을 개수 5로 나누면 6이다."},
    35: {"question": "산점도에서 한 변량이 증가할 때 다른 변량도 대체로 증가하는 경향을 무엇이라 하는가?", "choices": ["상관없다", "음의 상관관계", "양의 상관관계", "완전상관관계"], "answer_index": 2, "explanation": "함께 증가하는 경향은 양의 상관관계이다."},
    36: {"question": "(x+1)(x²-x+1)을 전개하면?", "choices": ["x³-1", "x³+x²+1", "x³+2x+1", "x³+1"], "answer_index": 3, "explanation": "합의 세제곱 공식에 의해 x³+1이다."},
    37: {"question": "다항식 f(x)=x³-2x+1을 x-1로 나눈 나머지는?", "choices": ["0", "1", "-1", "2"], "answer_index": 0, "explanation": "나머지정리에 의해 f(1)=1-2+1=0이다."},
    38: {"question": "이차방정식 x²+4=0의 해는?", "choices": ["x=±2", "x=±2i", "x=±4i", "x=±i"], "answer_index": 1, "explanation": "x²=-4이므로 x=±√(-4)=±2i이다."},
    39: {"question": "이차방정식 x²-2x+5=0의 판별식 D의 값은?", "choices": ["16", "4", "-16", "-4"], "answer_index": 2, "explanation": "D=(-2)²-4×1×5=4-20=-16이다."},
    40: {"question": "연립부등식 x>1과 x<5를 동시에 만족하는 x의 범위는?", "choices": ["x<1", "x>5", "x<1 또는 x>5", "1<x<5"], "answer_index": 3, "explanation": "두 조건을 모두 만족하는 범위는 1<x<5이다."},
    41: {"question": "두 점 (0,0)과 (3,4) 사이의 거리는?", "choices": ["5", "7", "6", "4"], "answer_index": 0, "explanation": "√(3²+4²)=√25=5이다."},
    42: {"question": "중심이 원점이고 반지름이 3인 원의 방정식은?", "choices": ["x²+y²=3", "x²+y²=9", "x²+y²=6", "(x-3)²+y²=9"], "answer_index": 1, "explanation": "반지름 r인 원의 방정식은 x²+y²=r²이므로 x²+y²=9이다."},
    43: {"question": "점 (2,3)을 x축에 대하여 대칭이동한 점의 좌표는?", "choices": ["(-2,3)", "(-2,-3)", "(2,-3)", "(3,2)"], "answer_index": 2, "explanation": "x축 대칭이동은 y좌표의 부호만 바뀌므로 (2,-3)이다."},
    44: {"question": "전체집합 U={1,2,3,4,5}, A={1,2,3}일 때 A의 여집합 Aᶜ는?", "choices": ["{1,2,3}", "{1,2,3,4,5}", "∅", "{4,5}"], "answer_index": 3, "explanation": "여집합은 U에서 A를 제외한 원소들의 집합이다."},
    45: {"question": "f(x)=2x+1, g(x)=x-3일 때 (f∘g)(3)의 값은?", "choices": ["1", "3", "7", "-1"], "answer_index": 0, "explanation": "g(3)=0이므로 f(0)=1이다."},
    46: {"question": "함수 y=1/(x-2)의 그래프에서 수직점근선은?", "choices": ["x=-2", "x=2", "y=2", "y=-2"], "answer_index": 1, "explanation": "분모가 0이 되는 x=2가 수직점근선이다."},
    47: {"question": "서로 다른 4명 중 2명을 뽑아 일렬로 세우는 경우의 수는?", "choices": ["6", "8", "12", "24"], "answer_index": 2, "explanation": "₄P₂=4×3=12이다."},
    48: {"question": "log₂8의 값은?", "choices": ["2", "4", "8", "3"], "answer_index": 3, "explanation": "2³=8이므로 log₂8=3이다."},
    49: {"question": "방정식 2ˣ=8을 만족하는 x의 값은?", "choices": ["3", "4", "2", "8"], "answer_index": 0, "explanation": "2³=8이므로 x=3이다."},
    50: {"question": "sin(π/2)의 값은?", "choices": ["0", "1", "-1", "1/2"], "answer_index": 1, "explanation": "π/2는 90°이므로 sin값은 1이다."},
    51: {"question": "삼각형에서 a=2, b=3, 끼인각 C=60°일 때 코사인법칙으로 구한 c²의 값은?", "choices": ["13", "5", "7", "1"], "answer_index": 2, "explanation": "c²=4+9-2×2×3×cos60°=13-6=7이다."},
    52: {"question": "첫째항이 2, 공차가 3인 등차수열의 다섯 번째 항은?", "choices": ["11", "12", "17", "14"], "answer_index": 3, "explanation": "a₅=2+4×3=14이다."},
    53: {"question": "∑(k=1부터 5까지) k의 값은?", "choices": ["15", "10", "20", "25"], "answer_index": 0, "explanation": "1+2+3+4+5=15이다."},
    54: {"question": "lim(x→2) (x²-4)/(x-2)의 값은?", "choices": ["2", "4", "0", "∞"], "answer_index": 1, "explanation": "인수분해하면 (x-2)(x+2)/(x-2)=x+2이므로 극한값은 4이다."},
    55: {"question": "f(x)=x²일 때 f'(3)의 값은?", "choices": ["3", "9", "6", "2"], "answer_index": 2, "explanation": "f'(x)=2x이므로 f'(3)=6이다."},
    56: {"question": "곡선 y=x²의 x=1에서의 접선의 기울기는?", "choices": ["1", "0", "4", "2"], "answer_index": 3, "explanation": "y'=2x이므로 x=1에서 기울기는 2이다."},
    57: {"question": "∫2x dx를 계산하면?", "choices": ["x²+C", "2x²+C", "x²+2x+C", "2+C"], "answer_index": 0, "explanation": "2x를 적분하면 x²+C이다."},
    58: {"question": "∫(0부터 2까지) x dx의 값은?", "choices": ["1", "2", "4", "0"], "answer_index": 1, "explanation": "[x²/2]를 0부터 2까지 계산하면 2이다."},
    59: {"question": "서로 다른 3개 중에서 중복을 허락하여 2개를 택하는 중복조합 ₃H₂의 값은?", "choices": ["3", "9", "6", "12"], "answer_index": 2, "explanation": "₃H₂=C(3+2-1,2)=C(4,2)=6이다."},
    60: {"question": "주사위를 한 번 던질 때 짝수의 눈이 나올 확률은?", "choices": ["1/3", "1/6", "2/3", "1/2"], "answer_index": 3, "explanation": "짝수는 2,4,6의 3가지이므로 확률은 3/6=1/2이다."},
    61: {"question": "P(A)=0.5, P(A∩B)=0.2일 때 조건부확률 P(B|A)의 값은?", "choices": ["0.4", "0.2", "0.5", "0.1"], "answer_index": 0, "explanation": "P(B|A)=P(A∩B)/P(A)=0.2/0.5=0.4이다."},
    62: {"question": "확률변수 X가 P(X=0)=0.3, P(X=1)=0.7일 때 기댓값 E(X)의 값은?", "choices": ["0.3", "0.7", "1", "0.5"], "answer_index": 1, "explanation": "E(X)=0×0.3+1×0.7=0.7이다."},
    63: {"question": "정규분포 N(50, 4²)을 따르는 X=58을 표준화한 Z값은?", "choices": ["1", "4", "2", "8"], "answer_index": 2, "explanation": "Z=(58-50)/4=2이다."},
    64: {"question": "표본의 크기 n이 커질수록 표본평균의 표준오차(σ/√n)는 어떻게 변하는가?", "choices": ["커진다", "변하지 않는다", "일정하게 유지된다", "작아진다"], "answer_index": 3, "explanation": "n이 커지면 분모 √n이 커져 표준오차는 작아진다."},
    65: {"question": "급수 ∑(n=1부터 ∞까지) (1/2)ⁿ의 합은?", "choices": ["1", "2", "1/2", "∞"], "answer_index": 0, "explanation": "첫항 1/2, 공비 1/2인 등비급수의 합은 a/(1-r)=1이다."},
    66: {"question": "f(x)=sin x의 도함수는?", "choices": ["-sin x", "cos x", "-cos x", "sin x"], "answer_index": 1, "explanation": "sin x를 미분하면 cos x이다."},
    67: {"question": "x=t², y=2t로 나타낸 곡선에서 dy/dx는?", "choices": ["t", "2t", "1/t", "2/t²"], "answer_index": 2, "explanation": "dy/dt=2, dx/dt=2t이므로 dy/dx=2/(2t)=1/t이다."},
    68: {"question": "치환적분(u=x²)을 이용해 ∫2x cos(x²) dx를 구하면?", "choices": ["cos(x²)+C", "-sin(x²)+C", "x²sin(x²)+C", "sin(x²)+C"], "answer_index": 3, "explanation": "u=x²로 치환하면 du=2x dx이므로 ∫cos u du=sin u+C=sin(x²)+C이다."},
    69: {"question": "타원 x²/9+y²/4=1에서 장축의 길이는?", "choices": ["6", "4", "9", "3"], "answer_index": 0, "explanation": "a²=9이므로 a=3, 장축의 길이는 2a=6이다."},
    70: {"question": "벡터 a=(1,2), b=(3,-1)일 때 a·b의 값은?", "choices": ["5", "1", "-1", "7"], "answer_index": 1, "explanation": "a·b=1×3+2×(-1)=3-2=1이다."},
}


def main():
    conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id FROM curriculum_topics')
            existing_ids = {row['id'] for row in cursor.fetchall()}

            total, skipped = 0, 0
            for topic_id, q in QUIZ.items():
                if topic_id not in existing_ids:
                    skipped += 1
                    continue
                cursor.execute(
                    '''INSERT INTO curriculum_quiz (topic_id, question, choices, answer_index, explanation)
                       VALUES (%s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                         question = VALUES(question), choices = VALUES(choices),
                         answer_index = VALUES(answer_index), explanation = VALUES(explanation)''',
                    (topic_id, q['question'], json.dumps(q['choices'], ensure_ascii=False), q['answer_index'], q['explanation'])
                )
                total += 1
            conn.commit()
            print(f'시드 완료: {total}개 문제 (건너뜀: {skipped}개)')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
