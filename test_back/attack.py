from fastapi import FastAPI, Request, HTTPException
import uvicorn
import logging
import json
import os
import asyncio
import aiohttp
from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import jsonify
import requests

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("received_logs.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LogReceiver")

# FastAPI 앱 생성
app = FastAPI(title="Log Receiver API", description="외부 서버로부터 로그를 수신하는 API")

# 설정 변수
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8080))
LOG_FILE = os.environ.get("LOG_FILE", "detailed_logs.json")
FORWARD_TARGET_URL = os.environ.get("FORWARD_URL", "http://localhost:8081/api/log")
FORWARD_ENABLED = os.environ.get("FORWARD_ENABLED", "true").lower() in ("true", "1", "yes", "y")
FORWARD_TIMEOUT = int(os.environ.get("FORWARD_TIMEOUT", "5"))  # 초 단위

# 로그 저장 함수
def save_log_to_file(log_data):
    """상세 로그를 JSON 파일에 저장"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "data": log_data
        }
        
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"로그 저장 중 오류: {e}")

# 로그 데이터 모델
class LogEntry(BaseModel):
    timestamp: Optional[str] = None
    source: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None
    additional_data: Optional[Dict[str, Any]] = None

# 여러 로그 항목을 한번에 받는 모델
class LogBatch(BaseModel):
    logs: List[LogEntry]

@app.get("/")
async def root():
    """API 루트 엔드포인트"""
    return {"status": "online", "message": "Log Receiver API is running"}

@app.post("/api/log")
async def receive_log(request: Request):
    """요청을 받아서 body에 명시된 path로 동적으로 전달"""
    try:
        # 요청 본문 읽기
        body = await request.body()
        body_text = body.decode('utf-8', errors='ignore')
        
        print("\n===== 수신된 요청 =====")
        print(f"헤더: {dict(request.headers)}")
        print(f"본문: {body_text}")
        
        # JSON 파싱
        try:
            data = json.loads(body_text)
            
            # path 추출
            if "path" not in data:
                raise HTTPException(status_code=400, detail="요청 본문에 path가 없습니다")
                
            target_path = data.get("path")
            method = data.get("method", "GET")
            request_body = data.get("body")
            request_headers = data.get("headers", {})
            host_value = request_headers.get("Host") or request_headers.get("host")
            if not host_value:
                host_value = "127.0.0.1"
            print(f"추출된 Host 헤더: {host_value}")
            # 대상 URL 구성
            target_url = f"http://{host_value}{target_path}"
            
            print(f"\n===== 전달 정보 =====")
            print(f"대상 URL: {target_url}")
            print(f"메서드: {method}")
            print(f"헤더: {request_headers}")
            print(f"본문: {request_body}")
            
            # HTTP 메서드에 따라 요청 전달
            response = None
            
            if method == "GET":
                response = requests.get(target_url, headers=request_headers)
            elif method == "POST":
                response = requests.post(target_url, json=request_body, headers=request_headers)
            elif method == "PUT":
                response = requests.put(target_url, json=request_body, headers=request_headers)
            elif method == "DELETE":
                response = requests.delete(target_url, headers=request_headers)
            elif method == "PATCH":
                response = requests.patch(target_url, json=request_body, headers=request_headers)
            else:
                raise HTTPException(status_code=400, detail=f"지원하지 않는 HTTP 메서드: {method}")
            
            print("\n===== 전달 결과 =====")
            print(f"상태 코드: {response.status_code}")
            print(f"응답: {response.text[:200]}")
            
            return {
                "status": "success", 
                "message": "요청 전달 완료",
                "response_status": response.status_code,
                "response_text": response.text[:200]
            }
            
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="JSON 파싱 실패")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        # FastAPI에서는 jsonify를 사용하지 않고 dict를 반환
        return {"status": "error", "message": str(e)}

def main():
    """API 서버 시작"""
    logger.info(f"Log Receiver API 시작 중: {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=8080)

if __name__ == "__main__":
    main()