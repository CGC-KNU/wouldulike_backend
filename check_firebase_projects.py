#!/usr/bin/env python
"""
Firebase 프로젝트 ID 확인 스크립트
서비스 계정 파일에서 프로젝트 ID를 추출합니다.
"""
import json
import os
import sys
from pathlib import Path

def check_service_account_file(file_path):
    """서비스 계정 파일에서 프로젝트 ID 확인"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        project_id = data.get('project_id')
        project_number = data.get('project_number')
        client_email = data.get('client_email', '').split('@')[0] if data.get('client_email') else 'N/A'
        
        return {
            'file': file_path,
            'project_id': project_id,
            'project_number': project_number,
            'client_email': client_email,
            'valid': True
        }
    except FileNotFoundError:
        return {'file': file_path, 'valid': False, 'error': 'File not found'}
    except json.JSONDecodeError:
        return {'file': file_path, 'valid': False, 'error': 'Invalid JSON'}
    except Exception as e:
        return {'file': file_path, 'valid': False, 'error': str(e)}


def find_service_account_files(search_dirs=None):
    """서비스 계정 파일 찾기"""
    if search_dirs is None:
        search_dirs = [
            '.',
            './config',
            './secrets',
            './credentials',
            os.path.expanduser('~/.config/firebase'),
        ]
    
    found_files = []
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
        
        for root, dirs, files in os.walk(search_dir):
            # .git, node_modules 등 제외
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__pycache__', '.venv', 'venv']]
            
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            # 서비스 계정 파일인지 확인 (project_id와 private_key가 있으면)
                            if 'project_id' in data and 'private_key' in data:
                                found_files.append(file_path)
                    except:
                        pass
    
    return found_files


def main():
    print("=" * 60)
    print("Firebase 프로젝트 ID 확인 도구")
    print("=" * 60)
    print()
    
    # 1. 환경변수에서 확인
    print("1. 환경변수에서 확인:")
    fcm_project_id = os.getenv("FCM_PROJECT_ID")
    fcm_service_account_file = os.getenv("FCM_SERVICE_ACCOUNT_FILE")
    
    if fcm_project_id:
        print(f"   FCM_PROJECT_ID: {fcm_project_id}")
    if fcm_service_account_file:
        print(f"   FCM_SERVICE_ACCOUNT_FILE: {fcm_service_account_file}")
        if os.path.exists(fcm_service_account_file):
            result = check_service_account_file(fcm_service_account_file)
            if result['valid']:
                print(f"   → 프로젝트 ID: {result['project_id']}")
                print(f"   → 프로젝트 번호: {result['project_number']}")
    print()
    
    # 2. 명령줄 인자로 파일 경로 제공 시
    if len(sys.argv) > 1:
        print("2. 지정된 파일 확인:")
        for file_path in sys.argv[1:]:
            result = check_service_account_file(file_path)
            if result['valid']:
                print(f"   파일: {result['file']}")
                print(f"   프로젝트 ID: {result['project_id']}")
                print(f"   프로젝트 번호: {result['project_number']}")
                print(f"   서비스 계정: {result['client_email']}")
                print()
            else:
                print(f"   파일: {result['file']}")
                print(f"   오류: {result.get('error', 'Unknown error')}")
                print()
    
    # 3. 자동으로 서비스 계정 파일 찾기
    print("3. 자동 검색 중...")
    found_files = find_service_account_files()
    
    if found_files:
        print(f"   {len(found_files)}개의 서비스 계정 파일을 찾았습니다:\n")
        projects = []
        for file_path in found_files:
            result = check_service_account_file(file_path)
            if result['valid']:
                projects.append(result)
                print(f"   파일: {result['file']}")
                print(f"   프로젝트 ID: {result['project_id']}")
                print(f"   프로젝트 번호: {result['project_number']}")
                print()
        
        # 중복 제거하여 프로젝트 목록 출력
        unique_projects = {}
        for p in projects:
            if p['project_id'] not in unique_projects:
                unique_projects[p['project_id']] = p
        
        print("=" * 60)
        print("발견된 Firebase 프로젝트 목록:")
        print("=" * 60)
        for project_id, info in unique_projects.items():
            print(f"프로젝트 ID: {project_id}")
            print(f"  파일: {info['file']}")
            print(f"  프로젝트 번호: {info['project_number']}")
            print()
        
        # 설정 예시 출력
        print("=" * 60)
        print("FCM_PROJECT_CONFIGS 설정 예시:")
        print("=" * 60)
        configs = []
        for project_id, info in unique_projects.items():
            configs.append({
                "project_id": project_id,
                "service_account_file": info['file']
            })
        print(json.dumps(configs, indent=2, ensure_ascii=False))
    else:
        print("   서비스 계정 파일을 찾을 수 없습니다.")
        print()
        print("수동으로 확인하는 방법:")
        print("1. Firebase Console (https://console.firebase.google.com/) 접속")
        print("2. 프로젝트 설정 > 서비스 계정 메뉴")
        print("3. '새 비공개 키 생성'으로 서비스 계정 파일 다운로드")
        print("4. 다운로드한 파일에서 'project_id' 확인")


if __name__ == "__main__":
    main()

