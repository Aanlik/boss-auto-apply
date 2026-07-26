import type { RefObject } from "react";
import type { CompanyBlacklistItem } from "../lib/types";

type CompanyBlacklistPanelProps = {
  companies: CompanyBlacklistItem[];
  inputValue: string;
  expanded: boolean;
  importInputRef: RefObject<HTMLInputElement | null>;
  onInputChange: (value: string) => void;
  onAdd: (name: string) => void;
  onRemove: (name: string) => void;
  onToggleExpanded: () => void;
  onExport: () => void;
  onImport: (file?: File) => void;
};

export function CompanyBlacklistPanel({
  companies,
  inputValue,
  expanded,
  importInputRef,
  onInputChange,
  onAdd,
  onRemove,
  onToggleExpanded,
  onExport,
  onImport,
}: CompanyBlacklistPanelProps) {
  const visibleCompanies = expanded ? companies : companies.slice(0, 3);

  return (
    <div className="blacklist-box">
      <div className="blacklist-manager__header">
        <div>
          <label className="field-label" htmlFor="company-blacklist-input">企业黑名单</label>
          <p className="blacklist-count">已维护 {companies.length} 家</p>
        </div>
        <div className="blacklist-actions">
          <button type="button" className="button-quiet button-compact" onClick={onExport}>导出</button>
          <button type="button" className="button-quiet button-compact" onClick={() => importInputRef.current?.click()}>导入</button>
        </div>
      </div>
      <div className="blacklist-content">
        <div className="blacklist-entry">
          <div className="blacklist-entry-row">
            <input
              id="company-blacklist-input"
              className="form-input form-input--inline"
              value={inputValue}
              onChange={e => onInputChange(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") onAdd(inputValue); }}
              placeholder="输入工商注册名称"
            />
            <button type="button" className="button-secondary" onClick={() => onAdd(inputValue)}>加入</button>
          </div>
        </div>
        <div className="blacklist-manager">
          <div className={companies.length === 0 ? "blacklist-empty" : "blacklist-tags"}>
            {companies.length === 0 ? (
              <span>暂无黑名单企业</span>
            ) : visibleCompanies.map(item => (
              <span key={item.name} className="tag tag--red tag--removable">
                <span>{item.name}</span>
                <button
                  type="button"
                  className="tag-remove-button"
                  aria-label={`从企业黑名单删除 ${item.name}`}
                  title="从企业黑名单删除"
                  onClick={() => onRemove(item.name)}
                >×</button>
              </span>
            ))}
            {companies.length > 3 && (
              <button type="button" className="button-quiet button-compact" onClick={onToggleExpanded}>
                {expanded ? "收起名单" : `展开全部 ${companies.length} 家`}
              </button>
            )}
          </div>
          <input
            ref={importInputRef}
            type="file"
            accept="application/json,.json"
            style={{ display: "none" }}
            onChange={e => onImport(e.target.files?.[0])}
          />
        </div>
      </div>
    </div>
  );
}
