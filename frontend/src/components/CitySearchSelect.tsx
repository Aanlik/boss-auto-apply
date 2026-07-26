import { useEffect, useMemo, useRef, useState } from "react";


type CitySearchSelectProps = {
  value: string;
  options: string[];
  onChange: (value: string) => void;
  label?: string;
};


export function CitySearchSelect({ value, options, onChange, label = "城市" }: CitySearchSelectProps) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  const filtered = useMemo(() => {
    const clean = query.trim().toLowerCase();
    const source = clean
      ? options.filter(city => city.toLowerCase().includes(clean))
      : options;
    const selectedFirst = value && source.includes(value)
      ? [value, ...source.filter(city => city !== value)]
      : source;
    return selectedFirst.slice(0, 30);
  }, [options, query, value]);

  function selectCity(next: string) {
    onChange(next);
    setQuery(next);
    setOpen(false);
  }

  return (
    <div className="city-search" ref={rootRef}>
      <input
        aria-label={label}
        className="form-input form-input--inline city-search__input"
        value={query}
        placeholder="搜索城市"
        autoComplete="off"
        onFocus={() => setOpen(true)}
        onChange={e => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onKeyDown={e => {
          if (e.key === "Enter" && filtered[0]) {
            e.preventDefault();
            selectCity(filtered[0]);
          }
          if (e.key === "Escape") {
            setQuery(value);
            setOpen(false);
          }
        }}
      />
      {open && (
        <div className="city-search__menu" role="listbox" aria-label={`${label}列表`}>
          {filtered.length > 0 ? filtered.map(city => (
            <button
              key={city}
              type="button"
              role="option"
              aria-selected={city === value}
              className={city === value ? "city-search__option city-search__option--active" : "city-search__option"}
              onClick={() => selectCity(city)}
            >
              {city}
            </button>
          )) : (
            <div className="city-search__empty">没有匹配城市</div>
          )}
        </div>
      )}
    </div>
  );
}
