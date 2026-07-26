import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { CitySearchSelect } from "./CitySearchSelect";


describe("CitySearchSelect", () => {
  test("filters city options by typed keyword and selects a city", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <CitySearchSelect
        value="全国"
        options={["全国", "北京", "上海", "阿克苏地区", "澳门", "郑州"]}
        onChange={onChange}
      />
    );

    const input = screen.getByLabelText("城市");
    await user.clear(input);
    await user.type(input, "阿克");

    expect(screen.getByRole("option", { name: "阿克苏地区" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "澳门" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("option", { name: "阿克苏地区" }));

    expect(onChange).toHaveBeenCalledWith("阿克苏地区");
  });
});
