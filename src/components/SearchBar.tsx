interface Props {
  value: string;
  onChange: (v: string) => void;
  loading?: boolean;
}

export function SearchBar({ value, onChange, loading }: Props) {
  return (
    <div className={`searchbar ${loading ? "searchbar--loading" : ""}`}>
      <span className="searchbar__icon">⌘K</span>
      <input
        type="text"
        className="searchbar__input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="한자 / 한글 음 / 단어 / 병음"
        autoFocus
        spellCheck={false}
      />
      {value && (
        <button
          type="button"
          className="searchbar__clear"
          onClick={() => onChange("")}
          aria-label="지우기"
        >
          ✕
        </button>
      )}
    </div>
  );
}
