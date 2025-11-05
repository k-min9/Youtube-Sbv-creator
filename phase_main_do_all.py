"""
Phase Main: phase 01과 02 통합 처리 스크립트
대사 텍스트와 시퀀스 파일을 선택하면 JSON 변환부터 SBV 자막 생성까지 모든 과정을 한 번에 처리

필요 input (예시)
1. 대사 데이터 파일 선택 (desktop_arona_15_070ver_data.txt)
2. 시퀀스 파일 선택 (desktop_arona_15_070ver_sequence.txt)

작업 순서:
1. desktop_arona_15_070ver_data.txt 선택 → JSON 변환
2. desktop_arona_15_070ver_sequence.txt 선택 → SBV 자막 생성
3. 한국어, 영어, 일본어 자막 파일 자동 생성
"""
import json
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional

# GUI가 가능한 환경인지 체크
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    print("⚠️ tkinter를 사용할 수 없습니다. 기본 파일 경로를 사용합니다.")


# ===== Phase 1: 대사 파싱 클래스 =====
class DialogueParser:
    """대사 텍스트를 파싱하여 JSON으로 변환하는 클래스"""
    
    def __init__(self, input_file: str):
        """
        Args:
            input_file: 입력 텍스트 파일 경로
        """
        self.input_file = Path(input_file)
        self.dialogues = []
        
    def parse_file(self) -> List[Dict]:
        """텍스트 파일을 파싱하여 대사 리스트 생성"""
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 줄 단위로 처리
        i = 0
        while i < len(lines):
            # 빈 줄은 건너뛰기
            if not lines[i].strip():
                i += 1
                continue
            
            # 캐릭터명과 대사 분리 (첫 번째 줄)
            first_line = lines[i].strip()
            if ' : ' in first_line:
                # 4줄 묶음으로 처리
                dialogue_group = self._parse_dialogue_group(lines[i:i+4])
                if dialogue_group:
                    self.dialogues.append(dialogue_group)
                    i += 4
                else:
                    i += 1
            else:
                i += 1
                
        return self.dialogues
    
    def _parse_dialogue_group(self, lines: List[str]) -> Dict:
        """4줄의 대사 그룹을 파싱하여 딕셔너리로 변환"""
        if len(lines) < 4:
            return None
            
        # 언어 순서
        languages = ['ko', 'ja', 'ja_hiragana', 'en']
        dialogue_dict = {
            'character': None,
            'lines': {}
        }
        
        for idx, line in enumerate(lines[:4]):
            line = line.strip()
            if not line:
                continue
                
            # 캐릭터명과 대사 분리
            if ' : ' in line:
                parts = line.split(' : ', 1)
                character = parts[0].strip()
                text = parts[1].strip() if len(parts) > 1 else ''
                
                # 첫 번째 줄에서 캐릭터명 설정
                if idx == 0:
                    dialogue_dict['character'] = character
                
                # 각 언어별로 대사 저장
                if idx < len(languages):
                    dialogue_dict['lines'][languages[idx]] = text
            else:
                # ':' 가 없는 경우 (이어지는 대사일 수 있음)
                if idx < len(languages):
                    dialogue_dict['lines'][languages[idx]] = line
                    
        # 모든 언어가 있는지 확인
        if len(dialogue_dict['lines']) == 4 and dialogue_dict['character']:
            return dialogue_dict
        
        return None


# ===== Phase 2: SBV 변환 클래스 =====
class SBVConverter:
    """시퀀스 파일을 SBV 자막으로 변환하는 클래스"""
    
    def __init__(self, sequence_file: str, dialogue_data: List[Dict]):
        """
        Args:
            sequence_file: 시퀀스 파일 경로
            dialogue_data: 파싱된 대사 데이터
        """
        self.sequence_file = Path(sequence_file)
        self.dialogue_data = dialogue_data
        self.dialogue_index_map = {}
        self.sequence_data = []
        self.missing_translations = {'ko': 0, 'en': 0, 'ja': 0}
        
        # 일본어 텍스트로 인덱싱
        self._build_dialogue_index()
        
    def _build_dialogue_index(self):
        """일본어 텍스트로 빠른 검색을 위한 인덱스 생성"""
        for idx, dialogue in enumerate(self.dialogue_data):
            ja_text = dialogue['lines']['ja']
            # 정규화: 공백, 줄바꿈 제거
            normalized = re.sub(r'\s+', '', ja_text)
            self.dialogue_index_map[normalized] = idx
            
    def convert_timecode(self, premiere_time: str) -> str:
        """프리미어 타임코드(HH;MM;SS;FF)를 SBV 형식(H:MM:SS.mmm)으로 변환"""
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
                
                # 다음 줄부터 텍스트 수집
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
        """SBV 형식의 자막 콘텐츠 생성"""
        sbv_lines = []
        missing_count = 0
        
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
                        missing_count += 1
            
            # 자막 텍스트 결합
            if caption_texts:
                sbv_lines.append('\n'.join(caption_texts))
            else:
                sbv_lines.append('')  # 빈 자막
                
            sbv_lines.append('')  # 빈 줄 추가
        
        # 번역 없음 카운트 저장
        self.missing_translations[language] = missing_count
            
        return '\n'.join(sbv_lines)


# ===== 메인 처리 클래스 =====
class MainProcessor:
    """전체 프로세스를 관리하는 메인 클래스"""
    
    def __init__(self):
        """초기화"""
        self.output_dir = Path.cwd() / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        self.data_file = None
        self.sequence_file = None
        self.dialogue_data = None
        
    def select_files_gui(self):
        """GUI로 파일 선택"""
        root = tk.Tk()
        root.withdraw()
        
        try:
            # 대사 데이터 파일 선택
            print("📂 대사 데이터 파일을 선택해주세요...")
            self.data_file = filedialog.askopenfilename(
                title="대사 데이터 파일(data.txt)을 선택해주세요",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ],
                initialdir=os.getcwd()
            )
            
            if not self.data_file:
                messagebox.showerror("오류", "대사 데이터 파일이 선택되지 않았습니다.")
                raise ValueError("대사 데이터 파일이 선택되지 않았습니다.")
            
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
                
        finally:
            root.destroy()
            
    def select_files_default(self):
        """기본 경로로 파일 선택 (GUI 사용 불가 시)"""
        uploads_dir = Path("/mnt/user-data/uploads")
        
        # 대사 데이터 파일 찾기
        data_files = list(uploads_dir.glob("*data*.txt"))
        if data_files:
            self.data_file = str(data_files[0])
        else:
            raise FileNotFoundError("대사 데이터 파일을 찾을 수 없습니다.")
            
        # 시퀀스 파일 찾기
        sequence_files = list(uploads_dir.glob("*sequence*.txt"))
        if sequence_files:
            self.sequence_file = str(sequence_files[0])
        else:
            raise FileNotFoundError("시퀀스 파일을 찾을 수 없습니다.")
            
    def process_all(self):
        """전체 처리 프로세스"""
        print("\n" + "=" * 60)
        print("🚀 통합 처리 시작")
        print("=" * 60)
        
        # Phase 1: 대사 파싱 및 JSON 생성
        print("\n[Phase 1] 대사 데이터 파싱")
        print("-" * 40)
        print(f"📄 입력: {self.data_file}")
        
        parser = DialogueParser(self.data_file)
        self.dialogue_data = parser.parse_file()
        
        # JSON 저장
        json_filename = Path(self.data_file).stem + "_dialogues.json"
        json_path = self.output_dir / json_filename
        
        output_data = {
            'total_dialogues': len(self.dialogue_data),
            'dialogues': self.dialogue_data
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
            
        print(f"✅ JSON 생성: {json_path}")
        print(f"   - 총 {len(self.dialogue_data)}개 대사 파싱 완료")
        
        # 캐릭터별 통계
        character_counts = {}
        for dialogue in self.dialogue_data:
            char = dialogue['character']
            character_counts[char] = character_counts.get(char, 0) + 1
        
        for char, count in sorted(character_counts.items()):
            print(f"   - {char}: {count}개")
        
        # Phase 2: 시퀀스 파싱 및 SBV 생성
        print("\n[Phase 2] 시퀀스 → SBV 자막 변환")
        print("-" * 40)
        print(f"📄 입력: {self.sequence_file}")
        
        converter = SBVConverter(self.sequence_file, self.dialogue_data)
        converter.parse_sequence_file()
        
        print(f"✅ {len(converter.sequence_data)}개 시퀀스 엔트리 파싱 완료")
        
        # 각 언어별 SBV 파일 생성
        base_name = Path(self.sequence_file).stem
        languages = {
            'ko': '한국어',
            'en': '영어',
            'ja': '일본어'
        }
        
        print("\n📝 자막 파일 생성 중...")
        
        for lang_code, lang_name in languages.items():
            sbv_content = converter.create_sbv_content(lang_code)
            sbv_filename = f"{base_name}_captions_{lang_code}.sbv"
            sbv_path = self.output_dir / sbv_filename
            
            with open(sbv_path, 'w', encoding='utf-8') as f:
                f.write(sbv_content)
                
            print(f"✅ {lang_name} 자막: {sbv_path}")
        
        # 최종 통계
        print("\n" + "=" * 60)
        print("📊 최종 결과")
        print("=" * 60)
        
        print(f"\n📁 출력 폴더: {self.output_dir}")
        
        print("\n📋 생성된 파일:")
        print(f"  1. JSON 대사: {json_filename}")
        print(f"  2. 한국어 자막: {base_name}_captions_ko.sbv")
        print(f"  3. 영어 자막: {base_name}_captions_en.sbv")
        print(f"  4. 일본어 자막: {base_name}_captions_ja.sbv")
        
        print("\n⚠️ 번역 없음 항목:")
        print(f"  - 한국어: {converter.missing_translations['ko']}개")
        print(f"  - 영어: {converter.missing_translations['en']}개")
        
        if converter.missing_translations['ja'] > 0:
            print(f"  - 일본어: {converter.missing_translations['ja']}개")
        
        print("\n✨ 모든 작업이 완료되었습니다!")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🎬 통합 자막 처리 도구 v1.0")
    print("=" * 60)
    print("\n대사 데이터와 시퀀스 파일을 선택하면")
    print("JSON 변환부터 SBV 자막 생성까지 한 번에 처리합니다.\n")
    
    try:
        processor = MainProcessor()
        
        # 파일 선택
        if GUI_AVAILABLE:
            processor.select_files_gui()
        else:
            print("⚠️ GUI를 사용할 수 없어 기본 경로를 사용합니다.")
            processor.select_files_default()
        
        # 전체 처리
        processor.process_all()
        
    except ValueError as e:
        print(f"\n❌ 오류: {e}")
    except FileNotFoundError as e:
        print(f"\n❌ 파일을 찾을 수 없습니다: {e}")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()