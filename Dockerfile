# Python 3.13.2 공식 이미지 사용
FROM python:3.13.2-slim

WORKDIR /app

COPY requirements.txt .

# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 파일 복사
COPY . .

# asyncio 정책 설정 환경변수 (Python 3.13에서 이벤트 루프 안정성을 위해)
ENV PYTHONDEVMODE=1

# 봇 실행
CMD ["python", "bot.py"]
