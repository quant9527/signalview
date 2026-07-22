"""Instrument groups management page (url_path=instrument_groups)."""
from __future__ import annotations

import streamlit as st

from data import (
    get_instrument_groups,
    create_instrument_group,
    delete_instrument_group,
    get_instrument_group_members,
    add_instrument_group_member,
    remove_instrument_group_member,
)
from utils import instrument_search_picker, checkbox_data_editor


def _handle_create_group(name: str, desc: str | None) -> bool:
    """Create a group. Returns True if created, False if name empty or already exists."""
    name = name.strip()
    if not name:
        st.warning("分组名称不能为空")
        return False
    if create_instrument_group(name, desc):
        st.success(f"分组 `{name}` 创建成功")
        st.rerun()
        return True
    st.warning(f"分组 `{name}` 可能已存在")
    return False


def page_instrument_groups() -> None:
    """Instrument groups (url_path=instrument_groups)."""
    st.set_page_config(layout="wide", page_title="Instrument Groups")
    st.header("自选股分组管理")
    st.caption("管理自定义标的分组，供 quant-lab 回测时通过 target=组名 自动选中")
    st.divider()

    groups_df = get_instrument_groups()

    col_left, col_right = st.columns([2, 1])

    with col_left:
        if groups_df.empty:
            st.info("请先创建分组")
        else:
            selected_group = st.selectbox(
                "选择分组",
                options=groups_df["name"].tolist(),
                key="manage_group_select",
            )

            members_df = get_instrument_group_members(selected_group)

            tab_members, tab_add = st.tabs(["📋 成员列表", "➕ 添加成员"])

            with tab_members:
                if members_df.empty:
                    st.info(f"分组 `{selected_group}` 暂无成员")
                else:
                    st.write(f"**{selected_group}** 共 {len(members_df)} 个标的")
                    display_df = members_df.copy()
                    display_df["操作"] = "移除"

                    event = st.dataframe(
                        display_df,
                        hide_index=True,
                        width='stretch',
                        column_config={
                            "exchange": st.column_config.TextColumn("交易所", width="small"),
                            "symbol": st.column_config.TextColumn("代码", width="small"),
                            "reverse": st.column_config.CheckboxColumn("reverse", width="small"),
                            "instrument_name": st.column_config.TextColumn("名称", width="medium"),
                            "created_at": st.column_config.DatetimeColumn("添加时间", width="medium"),
                        },
                        on_select="rerun",
                        selection_mode="multi-row",
                        key=f"members_table_{selected_group}",
                    )

                    selected_rows = event.selection.get("rows", [])
                    if selected_rows:
                        to_remove = members_df.iloc[selected_rows]
                        if st.button(
                            f"移除选中的 {len(to_remove)} 个标的",
                            type="primary",
                            key=f"remove_btn_{selected_group}",
                        ):
                            removed_count = 0
                            for _, row in to_remove.iterrows():
                                if remove_instrument_group_member(
                                    selected_group, row["exchange"], row["symbol"]
                                ):
                                    removed_count += 1
                            st.success(f"已移除 {removed_count} 个标的")
                            st.rerun()

            with tab_add:
                reverse_flag = st.checkbox(
                    "作为 reverse 标的添加",
                    key=f"reverse_flag_{selected_group}",
                    help="勾选后，添加到该分组的成员会标记为 reverse。",
                )
                selected = instrument_search_picker(key_prefix=f"ig_{selected_group}")
                if not selected.empty:
                    if st.button(
                        f"添加选中的 {len(selected)} 个标的到 `{selected_group}`",
                        key=f"add_search_btn_{selected_group}",
                    ):
                        added_count = 0
                        for _, row in selected.iterrows():
                            if add_instrument_group_member(
                                selected_group, row["exchange"], row["symbol"], reverse=reverse_flag
                            ):
                                added_count += 1
                        st.success(f"已添加 {added_count} 个标的")
                        st.rerun()

    with col_right:
        st.subheader("新建分组")
        with st.form("create_group_form", clear_on_submit=True):
            new_group_name = st.text_input("分组名称", placeholder="如 position")
            new_group_desc = st.text_input("描述", placeholder="可选")
            submitted = st.form_submit_button("创建分组", width='stretch')
            if submitted:
                _handle_create_group(new_group_name, new_group_desc.strip() or None)

    st.divider()
    st.subheader("分组列表")
    if not groups_df.empty:
        selected_for_delete = checkbox_data_editor(
            groups_df[["name", "member_count", "description"]],
            checkbox_label="删除",
            disabled=["name", "member_count", "description"],
            column_config_overrides={
                "name": st.column_config.TextColumn("分组名称", width="medium"),
                "member_count": st.column_config.NumberColumn("标的数", width="small"),
                "description": st.column_config.TextColumn("描述", width="large"),
            },
            key="groups_editor",
        )
        to_delete = selected_for_delete["name"].tolist()
        if to_delete:
            if st.button(f"删除选中的 {len(to_delete)} 个分组", type="primary", width='stretch'):
                deleted = 0
                for g in to_delete:
                    if delete_instrument_group(g):
                        deleted += 1
                st.success(f"已删除 {deleted} 个分组")
                st.rerun()
    else:
        st.info("暂无分组，请在下方新建分组。")