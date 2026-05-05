// 백엔드(Rust)와 동기화되는 데이터 타입.

export interface CharEntry {
  char: string;
  reading: string;
  meaning: string;
  radical?: string | null;
  radical_strokes?: number | null;
  stroke_count?: number | null;
  level_code: number;
  level_label: string;
  long_sound: boolean;
  pinyin?: string | null;
  pinyin_extra?: string[] | null;
  simplified?: string | null;
  traditional?: string | null;
  en_def?: string | null;
  word_count?: number | null;
}

export interface Sense {
  sense_no?: number | null;
  definition: string;
  category?: string | null;
}

export interface WordEntry {
  id: number;
  word: string;
  word_clean: string;
  homonym_no?: number | null;
  is_affix: boolean;
  hanja?: string | null;
  word_type?: string | null;
  pos?: string | null;
  pronunciation?: string | null;
  senses: Sense[];
}
