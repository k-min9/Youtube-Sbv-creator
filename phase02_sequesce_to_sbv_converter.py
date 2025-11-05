"""
Phase 2: 시퀀스 파일을 SBV 자막으로 변환
프리미어 프로 시퀀스 데이터와 JSON 대사 데이터를 매칭하여 
한국어/영어 SBV 자막 파일 생성

입력 파일 형식 (desktop_arona_15_070ver_sequence.txt):
----------------------------------------
00;00;00;00 - 00;00;24;17
V7, 1
ver 0.7.0 out!

00;00;24;17 - 00;00;29;15
V5, 1
こんにちは。今回、m9devの代理を務めるアロナです。

00;00;29;15 - 00;00;36;09
V5, 1
こんにちは。今回、m9devの代理を務めるアロナです。
V5, 2
はじめまして。アロナ先輩のパートナーを担当するAI、プラナです。
----------------------------------------

SBV 출력 형식:
----------------------------------------
0:00:24.170,0:00:29.150
안녕하세요. 이번에 m9dev의 대리를 맡은 아로나입니다.

0:00:29.150,0:00:36.090
안녕하세요. 이번에 m9dev의 대리를 맡은 아로나입니다.
안녕하십니까. 아로나 선배의 파트너 역할을 맡은 AI 프라나입니다.
----------------------------------------
"""

import json
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# GUI가 가능한 환경인지 체크
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    print("⚠️ tkinter를 사용할 수 없습니다. 기본 파일 경로를 사용합니다.")


class SBVConverter:
    """시퀀스 파일을 SBV 자막으로 변환하는 클래스"""
    
    def __init__(self):
        """초기화"""
        self.sequence_data = []
        self.dialogue_data = {}
        self.dialogue_index_map = {}  # 일본어 텍스트로 대사 매핑
        self.output_dir = Path.cwd() / "output"
        self.output_dir.mkdir(exist_ok=True)
        
    def load_files_gui(self):
        """GUI 파일 다이얼로그로 파일 선택"""
        root = tk.Tk()
        root.withdraw()  # 메인 윈도우 숨기기
        
        try:
            # 시퀀스 파일 선택
            print("📂 시퀀스 파일을 선택해주세요...")
            self.sequence_file = filedialog.askopenfilename(
                title="시퀀스 파일(sequence.txt)을 선택해주세요",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ],
                initialdir=os.getcwd()
            )
            
            if not self.sequence_file:
                messagebox.showerror("오류", "시퀀스 파일이 선택되지 않았습니다.")
                raise ValueError("시퀀스 파일이 선택되지 않았습니다.")
            
            # JSON 파일 선택
            print("📂 JSON 대사 파일을 선택해주세요...")
            
            # output 폴더에 JSON 파일이 있는지 먼저 확인
            default_json_path = self.output_dir / "*.json"
            json_files = list(self.output_dir.glob("*_dialogues.json"))
            
            initial_dir = self.output_dir if json_files else os.getcwd()
            
            self.json_file = filedialog.askopenfilename(
                title="JSON 대사 파일(dialogues.json)을 선택해주세요",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("All files", "*.*")
                ],
                initialdir=initial_dir
            )
            
            if not self.json_file:
                messagebox.showerror("오류", "JSON 파일이 선택되지 않았습니다.")
                raise ValueError("JSON 파일이 선택되지 않았습니다.")
                
        finally:
            root.destroy()
            
        self._set_output_files()
        
    def load_files_default(self):
        """기본 경로로 파일 로드 (GUI 사용 불가 시)"""
        # 기본 파일 경로 설정
        uploads_dir = Path("/mnt/user-data/uploads")
        outputs_dir = Path("/mnt/user-data/outputs")
        
        # 시퀀스 파일 찾기
        sequence_files = list(uploads_dir.glob("*sequence*.txt"))
        if sequence_files:
            self.sequence_file = str(sequence_files[0])
        else:
            raise FileNotFoundError("시퀀스 파일을 찾을 수 없습니다.")
            
        # JSON 파일 찾기
        json_files = list(outputs_dir.glob("*dialogues.json"))
        if not json_files:
            json_files = list(Path.cwd().glob("output/*dialogues.json"))
        
        if json_files:
            self.json_file = str(json_files[0])
        else:
            raise FileNotFoundError("JSON 대사 파일을 찾을 수 없습니다.")
            
        self._set_output_files()
        
    def _set_output_files(self):
        """출력 파일 경로 설정"""
        print(f"📂 시퀀스 파일: {self.sequence_file}")
        print(f"📂 JSON 파일: {self.json_file}")
        
        # 파일명 기반 출력 파일 설정
        base_name = Path(self.sequence_file).stem
        self.output_ko = self.output_dir / f"{base_name}_captions_ko.sbv"
        self.output_en = self.output_dir / f"{base_name}_captions_en.sbv"
        self.output_ja = self.output_dir / f"{base_name}_captions_ja.sbv"
        
    def convert_timecode(self, premiere_time: str) -> str:
        """프리미어 타임코드(HH;MM;SS;FF)를 SBV 형식(H:MM:SS.mmm)으로 변환
        
        Args:
            premiere_time: "00;00;24;17" 형식의 타임코드
            
        Returns:
            "0:00:24.170" 형식의 SBV 타임코드
        """
        parts = premiere_time.split(';')
        if len(parts) != 4:
            return premiere_time
            
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        frames = int(parts[3])
        
        # 프레임을 밀리초로 변환 (30fps 기준)
        milliseconds = int((frames / 30.0) * 1000)
        
        # SBV 형식으로 변환
        return f"{hours}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        
    def parse_sequence_file(self):
        """시퀀스 파일 파싱"""
        with open(self.sequence_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        current_entry = None
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # 타임코드 라인 찾기 (00;00;00;00 - 00;00;24;17)
            if ' - ' in line and ';' in line:
                times = line.split(' - ')
                if len(times) == 2:
                    start_time = self.convert_timecode(times[0])
                    end_time = self.convert_timecode(times[1])
                    
                    # 현재 엔트리 저장 및 새 엔트리 시작
                    if current_entry and current_entry.get('texts'):
                        self.sequence_data.append(current_entry)
                    
                    current_entry = {
                        'start': start_time,
                        'end': end_time,
                        'texts': []
                    }
            
            # V5, V7 태그와 텍스트 파싱
            elif line.startswith('V') and ',' in line:
                # V5, 1 형식 파싱
                parts = line.split(',')
                speaker_type = parts[0].strip()
                speaker_num = parts[1].strip() if len(parts) > 1 else '1'
                
                # 다음 줄부터 텍스트 수집 (다음 V 태그나 타임코드까지)
                text_lines = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line:
                        break
                    if next_line.startswith('V') and ',' in next_line:
                        break
                    if ' - ' in next_line and ';' in next_line:
                        break
                    text_lines.append(next_line)
                    j += 1
                
                if text_lines and current_entry:
                    text = ' '.join(text_lines)
                    current_entry['texts'].append({
                        'speaker': f"{speaker_type}_{speaker_num}",
                        'text': text
                    })
                
                i = j - 1
                
            i += 1
        
        # 마지막 엔트리 저장
        if current_entry and current_entry.get('texts'):
            self.sequence_data.append(current_entry)
            
        print(f"✅ {len(self.sequence_data)}개의 시퀀스 엔트리 파싱 완료")
        
    def load_dialogue_json(self):
        """JSON 대사 파일 로드 및 인덱싱"""
        with open(self.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.dialogue_data = data['dialogues']
        
        # 일본어 텍스트로 빠른 검색을 위한 인덱스 생성
        for idx, dialogue in enumerate(self.dialogue_data):
            ja_text = dialogue['lines']['ja']
            # 정규화: 공백, 줄바꿈 제거
            normalized = re.sub(r'\s+', '', ja_text)
            self.dialogue_index_map[normalized] = idx
            
        print(f"✅ {len(self.dialogue_data)}개의 대사 로드 완료")
        
    def find_matching_dialogue(self, japanese_text: str) -> Optional[Dict]:
        """일본어 텍스트로 매칭되는 대사 찾기"""
        # 정규화
        normalized = re.sub(r'\s+', '', japanese_text)
        
        # 정확한 매칭 시도
        if normalized in self.dialogue_index_map:
            return self.dialogue_data[self.dialogue_index_map[normalized]]
            
        # 부분 매칭 시도 (앞부분 50자만)
        for key, idx in self.dialogue_index_map.items():
            if normalized[:50] in key or key in normalized:
                return self.dialogue_data[idx]
                
        return None
        
    def create_sbv_content(self, language: str) -> str:
        """SBV 형식의 자막 콘텐츠 생성
        
        Args:
            language: 'ko', 'en', 'ja' 중 하나
            
        Returns:
            SBV 형식의 문자열
        """
        sbv_lines = []
        
        for entry in self.sequence_data:
            # 타임코드 추가
            sbv_lines.append(f"{entry['start']},{entry['end']}")
            
            # 텍스트 추가
            caption_texts = []
            for text_entry in entry['texts']:
                japanese_text = text_entry['text']
                
                # 매칭되는 대사 찾기
                matched_dialogue = self.find_matching_dialogue(japanese_text)
                
                if matched_dialogue:
                    # 해당 언어의 텍스트 가져오기
                    if language in matched_dialogue['lines']:
                        caption_texts.append(matched_dialogue['lines'][language])
                else:
                    # 매칭 실패 시 원본 텍스트 사용 (일본어인 경우)
                    if language == 'ja':
                        caption_texts.append(japanese_text)
                    else:
                        # 다른 언어는 표시할 내용이 없으면 스킵
                        caption_texts.append(f"[번역 없음: {japanese_text[:30]}...]")
            
            # 자막 텍스트 결합
            if caption_texts:
                sbv_lines.append('\n'.join(caption_texts))
            else:
                sbv_lines.append('')  # 빈 자막
                
            sbv_lines.append('')  # 빈 줄 추가
            
        return '\n'.join(sbv_lines)
        
    def save_sbv_files(self):
        """각 언어별 SBV 파일 저장"""
        # 한국어 자막
        ko_content = self.create_sbv_content('ko')
        with open(self.output_ko, 'w', encoding='utf-8') as f:
            f.write(ko_content)
        print(f"✅ 한국어 자막 저장: {self.output_ko}")
        
        # 영어 자막
        en_content = self.create_sbv_content('en')
        with open(self.output_en, 'w', encoding='utf-8') as f:
            f.write(en_content)
        print(f"✅ 영어 자막 저장: {self.output_en}")
        
        # 일본어 자막 (보너스)
        ja_content = self.create_sbv_content('ja')
        with open(self.output_ja, 'w', encoding='utf-8') as f:
            f.write(ja_content)
        print(f"✅ 일본어 자막 저장: {self.output_ja}")
        
    def print_summary(self):
        """변환 결과 요약"""
        print("\n📊 변환 결과 요약")
        print("=" * 50)
        print(f"총 자막 엔트리: {len(self.sequence_data)}개")
        
        # 샘플 출력
        if self.sequence_data:
            print("\n📝 첫 번째 자막 샘플:")
            print("-" * 30)
            sample = self.sequence_data[0]
            print(f"시간: {sample['start']} → {sample['end']}")
            for text in sample['texts'][:2]:
                print(f"  화자: {text['speaker']}")
                print(f"  일본어: {text['text'][:50]}...")
                
                # 매칭된 한국어/영어 찾기
                matched = self.find_matching_dialogue(text['text'])
                if matched:
                    print(f"  한국어: {matched['lines']['ko'][:50]}...")
                    print(f"  영어: {matched['lines']['en'][:50]}...")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🎬 시퀀스 → SBV 자막 변환 도구")
    print("=" * 60)
    
    try:
        converter = SBVConverter()
        
        # GUI 사용 가능 여부에 따라 파일 로드 방식 결정
        if GUI_AVAILABLE:
            converter.load_files_gui()
        else:
            print("⚠️ GUI를 사용할 수 없어 기본 경로를 사용합니다.")
            converter.load_files_default()
        
        # 시퀀스 파싱
        print("\n🔄 시퀀스 파일 파싱 중...")
        converter.parse_sequence_file()
        
        # 대사 JSON 로드
        print("\n🔄 대사 데이터 로드 중...")
        converter.load_dialogue_json()
        
        # SBV 파일 생성
        print("\n🔄 자막 파일 생성 중...")
        converter.save_sbv_files()
        
        # 요약 출력
        converter.print_summary()
        
        print("\n✅ 모든 작업이 완료되었습니다!")
        print(f"📁 출력 폴더: {converter.output_dir}")
        
    except ValueError as e:
        print(f"❌ 오류: {e}")
    except FileNotFoundError as e:
        print(f"❌ 파일을 찾을 수 없습니다: {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()