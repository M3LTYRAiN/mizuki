# Python 3.13.2 공식 이미지 사용
FROM python:3.13.2-slim

WORKDIR /app

# 먼저 패키지 업데이트 및 필요한 라이브러리 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libfontconfig1 libharfbuzz0b \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 의존성 설치 (중복 제거)
RUN pip install --no-cache-dir -r requirements.txt

# 1. 먼저 필요한 디렉토리만 생성
RUN mkdir -p /app/OTF /app/im

# 2. 특정 폴더 먼저 복사
COPY OTF/ /app/OTF/
COPY im/ /app/im/

# 3. 나머지 파일 복사 (이미 복사된 파일 제외)
COPY *.py /app/
COPY requirements.txt /app/
# 나머지 필요한 파일들...

# 디렉토리 권한 설정 (실행 권한 추가)
RUN chmod -R 755 /app/OTF /app/im

# 디버깅: 파일 존재 여부 확인
RUN echo "=== 폰트 파일 확인 ===" && \
    find /app -name "*.ttf" && \
    echo "=== 이미지 파일 확인 ===" && \
    find /app -name "*.png"

# 필요한 디렉토리 생성 확인
RUN mkdir -p /app/OTF /app/im

# 디렉토리 내용 확인 (디버깅용)
RUN echo "=== 폰트 디렉토리 확인 ===" && \
    ls -la /app/OTF && \
    echo "=== 이미지 디렉토리 확인 ===" && \
    ls -la /app/im

# 폰트 및 이미지 파일 존재 확인
RUN find /app -name "*.ttf" | sort
RUN find /app -name "*.png" | sort

# asyncio 정책 설정 환경변수 (Python 3.13에서 이벤트 루프 안정성을 위해)
ENV PYTHONDEVMODE=1

# 경고 표시 억제를 위한 환경 변수 설정
ENV PYTHONWARNINGS="ignore::DeprecationWarning:disnake.http"

# 로케일 설정 추가
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
# 봇 실행CMD ["python", "bot.py"]