import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import { CompanyBlacklistPanel } from "./CompanyBlacklistPanel";

afterEach(() => cleanup());

describe("CompanyBlacklistPanel", () => {
  test("shows empty state and exposes import/export actions separately from the list", async () => {
    const user = userEvent.setup();
    const onAdd = vi.fn();
    const onExport = vi.fn();

    render(
      <CompanyBlacklistPanel
        companies={[]}
        inputValue=""
        expanded={false}
        importInputRef={{ current: null }}
        onInputChange={vi.fn()}
        onAdd={onAdd}
        onRemove={vi.fn()}
        onToggleExpanded={vi.fn()}
        onExport={onExport}
        onImport={vi.fn()}
      />
    );

    expect(screen.getByText("暂无黑名单企业")).toBeInTheDocument();
    expect(screen.getByText("已维护 0 家")).toBeInTheDocument();

    await user.click(screen.getByText("导出"));
    expect(onExport).toHaveBeenCalledOnce();
  });

  test("adds a company from the input", async () => {
    const user = userEvent.setup();
    const onAdd = vi.fn();

    render(
      <CompanyBlacklistPanel
        companies={[]}
        inputValue="示例科技有限公司"
        expanded={false}
        importInputRef={{ current: null }}
        onInputChange={vi.fn()}
        onAdd={onAdd}
        onRemove={vi.fn()}
        onToggleExpanded={vi.fn()}
        onExport={vi.fn()}
        onImport={vi.fn()}
      />
    );

    await user.click(screen.getByText("加入"));
    expect(onAdd).toHaveBeenCalledWith("示例科技有限公司");
  });
});
