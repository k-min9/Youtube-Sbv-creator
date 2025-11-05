"""
Phase 1: 텍스트 데이터를 JSON으로 변환
캐릭터별 대사를 구조화된 JSON 형식으로 저장

입력 파일 format 형식 (./input/자막 제작 프롬프트.txt):
----------------------------------------
arona : 안녕하세요. 이번에 m9dev의 대리를 맡은 아로나입니다.
arona : こんにちは。今回、m9devの代理を務めるアロナです。
arona : こんにちは。こんかい、えむきゅうでぶのだいりをつとめるあろなです。
arona : Hello. I'm Arona, representing m9dev this time.

plana : 안녕하십니까. 아로나 선배의 파트너 역할을 맡은 AI 프라나입니다.
plana : はじめまして。アロナ先輩のパートナーを担当するAI、プラナです。
plana : はじめまして。あろなせんぱいのぱーとなーをたんとうするえーあい、ぷらなです。
plana : Nice to meet you. I'm Plana, the AI partner working with Arona-senpai.
----------------------------------------

특징:
- 각 대사는 4줄로 구성 (ko, ja, ja_hiragana, en 순서)
- 캐릭터명 : 대사 형식
- 대사 그룹 사이에는 빈 줄이 있음
- 한 캐릭터가 여러 대사를 연속으로 할 수도 있음
"""

import json
import re
import os
from typing import List, Dict
from pathlib import Path
import tkinter as tk
from tkinter import filedialog


class DialogueParser:
    """대사 텍스트를 파싱하여 JSON으로 변환하는 클래스"""
    
    def __init__(self, input_file: str = None):
        """
        Args:
            input_file: 입력 텍스트 파일 경로 (None인 경우 파일 다이얼로그로 선택)
        """
        # 파일 다이얼로그로 입력 파일 선택
        if input_file is None:
            root = tk.Tk()
            root.withdraw()  # GUI 창 숨기기
            input_file = filedialog.askopenfilename(
                title="대사 텍스트 파일을 선택하세요",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ],
                initialdir=os.getcwd()
            )
            root.destroy()
            
            if not input_file:
                raise ValueError("파일이 선택되지 않았습니다.")
        
        self.input_file = Path(input_file)
        
        # 현재 디렉토리에 output 폴더 생성
        self.output_dir = Path.cwd() / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # 출력 파일명 설정 (input 파일명 기반)
        output_filename = self.input_file.stem + "_dialogues.json"
        self.output_file = self.output_dir / output_filename
        
        self.dialogues = []
        
        print(f"📂 입력 파일: {self.input_file}")
        print(f"📂 출력 폴더: {self.output_dir}")
        print(f"📄 출력 파일: {self.output_file}")
        
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
        """4줄의 대사 그룹을 파싱하여 딕셔너리로 변환
        
        Args:
            lines: 4줄의 텍스트 리스트
            
        Returns:
            파싱된 대사 딕셔너리
        """
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
    
    def save_to_json(self, pretty_print: bool = True):
        """파싱된 대사를 JSON 파일로 저장
        
        Args:
            pretty_print: 보기 좋게 들여쓰기 할지 여부
        """
        output_data = {
            'total_dialogues': len(self.dialogues),
            'dialogues': self.dialogues
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            if pretty_print:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            else:
                json.dump(output_data, f, ensure_ascii=False)
                
        print(f"✅ JSON 파일 저장 완료: {self.output_file}")
        print(f"   총 {len(self.dialogues)}개의 대사 그룹 파싱됨")
    
    def print_summary(self):
        """파싱 결과 요약 출력"""
        print("\n📊 파싱 결과 요약")
        print("=" * 50)
        
        # 캐릭터별 대사 수 집계
        character_counts = {}
        for dialogue in self.dialogues:
            char = dialogue['character']
            character_counts[char] = character_counts.get(char, 0) + 1
        
        print(f"총 대사 그룹 수: {len(self.dialogues)}개")
        print(f"등장 캐릭터 수: {len(character_counts)}명")
        print("\n캐릭터별 대사 수:")
        for char, count in sorted(character_counts.items()):
            print(f"  - {char}: {count}개")
        
        # 샘플 출력
        if self.dialogues:
            print("\n📝 첫 번째 대사 샘플:")
            print("-" * 30)
            sample = self.dialogues[0]
            print(f"캐릭터: {sample['character']}")
            for lang, text in sample['lines'].items():
                print(f"  [{lang}]: {text[:50]}..." if len(text) > 50 else f"  [{lang}]: {text}")


def main():
    """메인 실행 함수"""
    
    print("=" * 60)
    print("📚 대사 텍스트 → JSON 변환 도구")
    print("=" * 60)
    
    try:
        # 파서 생성 (파일 다이얼로그로 입력 파일 선택)
        parser = DialogueParser()  # input_file=None이면 자동으로 다이얼로그 표시
        
        print("\n🔄 파싱 시작...")
        dialogues = parser.parse_file()
        
        if not dialogues:
            print("⚠️ 파싱된 대사가 없습니다. 파일 형식을 확인해주세요.")
            return
        
        # JSON 저장
        parser.save_to_json(pretty_print=True)
        
        # 요약 출력
        parser.print_summary()
        
        # 검증을 위한 샘플 JSON 출력
        print("\n🔍 JSON 구조 샘플 (처음 2개):")
        sample_count = min(2, len(dialogues))
        print(json.dumps(dialogues[:sample_count], ensure_ascii=False, indent=2))
        
        print(f"\n✅ 모든 작업이 완료되었습니다!")
        print(f"📁 출력 파일 위치: {parser.output_file}")
        
    except ValueError as e:
        print(f"❌ 오류: {e}")
    except FileNotFoundError:
        print("❌ 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ 예상치 못한 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()