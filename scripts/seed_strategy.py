"""把 signal_lab_case 改名为 strategy_case，并写入 strategy.core_idea。

可重复执行。旧表名保留为视图，已部署的 signalview 仍能读案例。
核心思想根据 quant-lab 里对应策略的实现整理。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 名称与 strategy_case.strategy 一致。后缀 macd / ma5ma10 是分段口径，不是另一套思想。
CORE_IDEAS: dict[str, str] = {
    "active_vol": (
        "找近期放量上涨的活跃标的。最近约 20 根 K 线里，要出现成交量同时超过 "
        "5 日和 10 日均量两倍、且当天涨幅大于 5% 的日子；其后不能再出现阴线成交量"
        "盖过那根最大阳线。放量大阳说明有资金活跃，阴线量能更大则视为出货，不再入选。"
    ),
    "bc_xd4_macd": (
        "四段下跌背驰。用 MACD 金叉、死叉把走势切成下跌段，从近到远取连续四段，"
        "每一段的最低价和 MA5 最低值都要创出更早那些下跌段的新低。价格一波比一波低，"
        "但段的结构已经走出背驰，在这个位置买入。"
    ),
    "bc_xd4_ma5ma10": (
        "四段下跌背驰，分段改用 MA5 与 MA10 的金叉、死叉。从近到远连续四段下跌，"
        "每一段的最低价和 MA5 最低值都要创出前面下跌段的新低。思想与 bc_xd4_macd 相同，"
        "只是段的切分跟着短均线而不是 MACD。"
    ),
    "breakout_ma": (
        "收盘同一天从下方上穿 MA5 和 MA10，并且当天比对照组更强：对照组在跌，"
        "或者对照组虽然上涨但自己的价格还在 MA5、MA10 之下。同一天有多只股票满足时，"
        "按相对对照组的涨幅差打分，只买得分最高的两只。"
    ),
    "cl2b_pair": (
        "成对趋势里的二买。先用 MA5/MA10 找出两段连续抬高的上涨，再看右侧最近两到三段下跌，"
        "最近这段下跌要创出这几段下跌的新低，但低点仍高于第一段上涨的低点。"
        "后一段上涨里至少有一根涨幅达到 1%，并用 MA60、MACD 和 DIF 滤掉偏弱的结构。"
    ),
    "cl2b_surge": (
        "主升段消化完之后的再突破。在最近三个 MACD 上涨段里，找出红柱面积至少是另外两段两倍的那一段，"
        "把它当作当前行情的主升段。这段高点之后至少出现两次 MA5/MA10 死叉，而且高点一直没被突破。"
        "当天金叉或站上双均线时，若涨幅或连阳创出这段整理以来的新高，就买入。"
    ),
    "cl2b_triangle": (
        "上涨三角形整理后的向上突破。最近两个上涨段的高点都顶到布林上轨，上边几乎是平的；"
        "夹在中间的下跌段低点逐步抬高，下边在收敛。金叉或上穿短均线时买入。"
        "如果这段回调打到布林下轨，三角形已经被破坏，不买。"
    ),
    "cl2zs_ma5ma10": (
        "高点回落之后出现两个互不重叠的上涨中枢。用 MA5/MA10 分段，最近四段上涨里，"
        "较旧的两段价格重叠成一个中枢，较新的两段重叠成另一个，两个中枢的价格区间不相交；"
        "最近的下跌段还要打出近 50 根 K 线的新低。当天短均线金叉买入。"
        "持仓后如果个股转弱、对照指数却没有下跌，就卖出。"
    ),
    "cl3b_overlap_macd": (
        "价格回到中枢上沿时买入。用 MACD 从右向左找三段上涨：最右是离开段，"
        "它左边第一段力度明显更强的是中枢段，再往左是一段更长、低点不高于中枢的段落。"
        "当天最低价与中枢高点重叠，或者两者相差不到 1%，视为重新靠近中枢上沿。"
    ),
    "cl3b_seg_macd": (
        "用最近三段上涨表达三类买点。收盘要站上 MA5、MA10 和 MA20，并且当天从双均线下方同时上穿。"
        "MACD 上涨段里，最近一段的高点高于前一段，更早一段的高点和低点都低于中间段，"
        "最近下跌段的低点也不低于中间上涨段的高点。回调没有跌回前一段上涨内部。"
    ),
    "cl3b_seg_ma5ma10": (
        "段级三类买点，分段改用 MA5/MA10。收盘站上 MA5、MA10、MA20，并在当天从双均线下方同时上穿。"
        "最近一段上涨的高点高于前一段，更早一段整体低于中间段，最近下跌的低点不低于中间上涨段的高点。"
        "思想与 cl3b_seg_macd 相同，段跟着短均线切。"
    ),
    "cl3b_seg_surge_macd": (
        "下跌刚创新低、上涨力度却已经明显放大。最近两个 MACD 上涨段的 DIF 和 MACD 峰值大约放大到前一段的两倍，"
        "零轴下方的段也参加比较。当天或前一天的收盘、最低价创出最近下跌段的新低，同时今天站上 MA5 和 MA10。"
        "买的是新低处出现的强势反转，而不是等突破前高。"
    ),
    "cl3b_zs_macd": (
        "三类买点与中枢离开放在一起。用 MACD 分段跟踪中枢，临界可以是均线金叉、MACD 金叉或出水芙蓉，"
        "并要求价格离开中枢达到一定幅度。持仓期间如果 MACD 死叉或 MA5/MA10 死叉，就平仓。"
        "核心是中枢被离开之后的买点，而不是中枢内部的震荡。"
    ),
    "cl3b_zs_ma5ma10": (
        "三类买点与中枢离开，分段改用 MA5/MA10。在短均线切出的段上跟踪中枢，"
        "金叉、出水芙蓉等作为临界，离开中枢的幅度要达标。持仓后短均线或 MACD 死叉平仓。"
        "思想与 cl3b_zs_macd 相同。"
    ),
    "cl3b_zsx": (
        "大一段上涨之后，后面一小段涨不动，价格又落到两段之间的低点。最近两段上涨里，"
        "前一段的涨幅至少是最近一段的三倍，并且当前 K 线的最低价低于这两段之间的最低收盘价。"
        "买的是强势波段后的回落，而不是去追刚创出的高点。"
    ),
    "cmp_early_jc": (
        "个股比大盘先走强。大盘和个股都处在多段下跌里，个股已经先金叉；"
        "随后大盘收盘跌破前低，同一根 K 线上个股却不跌，收十字或上涨。"
        "对照的是沪深 300 一类指数，买的是大盘创新低时个股拒绝跟随的相对强弱。"
    ),
    "cmp_nfly_macd": (
        "大盘正在走一段下跌时，个股的回调更浅。这段大盘下跌期间，个股已经出现过一次 MA5/MA10 金叉，"
        "而且个股最近一个下跌段的 MA5 始终没有碰到再前一个下跌段的 MA5。"
        "MACD 用来确认段的位置。大盘 N 字下跌，个股没有把前一段的均线支撑跌穿。"
    ),
    "cmp_nfly_ma5ma10": (
        "大盘当前下跌段里，个股回调不破前一段均线。个股在这段大盘下跌中已经金叉过一次，"
        "最近一个下跌段的 MA5 碰不到再前一个下跌段的 MA5。分段口径是 MA5/MA10。"
        "思想与 cmp_nfly_macd 相同：指数在跌，个股的调整更浅。"
    ),
    "cmp_n_surge_ma5ma10": (
        "大盘走出下跌、上涨、再下跌，并且第二段下跌创新低时，个股也有同样的 N 字，"
        "但个股中间那段上涨的涨幅至少是它前一段上涨的两倍。在这段上涨之内，或它结束后的第一根 K 线，"
        "收盘上穿 MA5 就买入。买的是指数仍在 N 字下跌、个股中间段已经大幅加速的时刻。"
    ),
    "cmp_zs_macd": (
        "指数偏弱、个股偏强时，沿 MACD 段做三买或异动。收盘上穿 MA60，"
        "再用 MACD 上涨段比较突破段和它前一段的力度、死叉次数，以及这段区间里个股高点相对指数高点的强弱。"
        "满足异动或三买结构后买入。案例名沿用 cmp_zs_macd，实现在 cmp_seg。"
    ),
    "layup_long": (
        "快步创新高，慢步洗盘，正向标的。前一段上涨几乎不在 MA10 下方停留，一气呵成做出高点；"
        "随后的回调跌破这段的低点，并且收在 MA10 下方的 K 线数量至少是快段的两倍。"
        "快段代表拉升，慢段代表洗盘更充分，正向合约上记为 layup_long。"
    ),
    "layup_short": (
        "同一套快拉升、慢洗盘结构，用在反向标的上。前一段快速创新高，回调跌破前低，"
        "收在 MA10 下方的时间至少是拉升段的两倍。代码按合约是否 reverse 区分名称，"
        "反向标的记为 layup_short，结构判断与 layup_long 相同。"
    ),
    "macd_3bc_short": (
        "价格创新高、MACD 动能却一波比一波弱，用来做空。最近三段上涨的高点逐段抬高，"
        "各段 MACD 面积逐段缩小。当前 MACD 交叉作为临界。看的是上涨趋势末端的顶背驰，而不是下跌后的买入。"
    ),
    "ma_rebound": (
        "多头排列里的回踩二买。MA5 仍在 MA10 之上，当天最低价落到 MA10 以下，收盘却重新站上 MA5，"
        "并且收盘突破最近第二个上涨段的高点，而前一天还在那个高点之下。"
        "买的是回踩短均线之后、力度超过前一段上涨的反弹。"
    ),
    "nested_2bc_active": (
        "大级别背驰之后，用涨停和小级别再次买点确认。日线或 2 小时已经出现过 rebc，"
        "其后至少有一个涨停，再在 5 分钟或 15 分钟上出现 rebc 的那一根买入。"
        "大周期负责方向，涨停说明活跃，小周期负责入场时机。"
    ),
    "qs_zs": (
        "MACD 段上的浅回调和中枢离开。最近一段下跌相对前一段上涨的回撤要浅，"
        "左边一组下跌加上涨也要满足相应的幅度比例，最近下跌的低点要低于左侧第二个上涨段的高点。"
        "分钟和小时用更紧的幅度系数，日线放宽。买的是回调不深、仍贴着前一段结构的位置。"
    ),
    "rebc_bo": (
        "不再重新计算背驰，而是交易已经标出的 rebc 中枢边界。读取此前 rebc 信号里的中枢上沿和中枢下沿，"
        "当天成交量相对 10 日均量放大，收盘向上穿过其中一条边界就买入。"
        "核心是中枢被放量突破，而不是背驰本身。"
    ),
    "rebc_macd": (
        "中枢上的第一类买点。用 MACD 分段识别中枢、均线反复缠绕的湿吻，以及下跌背驰，"
        "价格离开中枢，但这段下跌不能深到已经脱离中枢。这是 rebc 的一买，后面的二买、三买和急涨都以它为起点。"
    ),
    "rebc_ma5ma10": (
        "中枢双级别背驰的一买，分段改用 MA5/MA10。在短均线切出的中枢里找湿吻和下跌背驰，"
        "离开中枢的跌幅要有限，不能已经跌离中枢下沿太远。思想与 rebc_macd 相同，段跟着短均线。"
    ),
    "rebc_ma5ma10_2b": (
        "一买之后的二买确认。此前已经有 rebc_ma5ma10 一买；前一根 K 线收阴，并且收在 MA5、MA10、MA20 之下，"
        "当天收盘站回 MA5 之上，当天涨幅还要盖过前一根的跌幅。回踩之后重新站上短均线，二买才算完成。"
    ),
    "rebc_ma5ma10_2b_pending": (
        "一买之后的二买还没有确认。已经有 rebc_ma5ma10 一买，当天收阴，收盘同时落到 MA5、MA10、MA20 之下，"
        "前一根也在 MA5 和 MA10 之下。这里只记下仍在均线下方的回踩，还没有站回去。"
    ),
    "rebc_ma5ma10_3b": (
        "一买之后的三类买点。出现 MA5/MA10 金叉，最近一个下跌段的低点没有碰到一买当时的中枢下沿，"
        "并且这段下跌左边相邻上涨段的 MA5 与 MA10 张口，是中枢以来最大的一次。"
        "回踩不破中枢下沿，视为离开中枢后的三类买。"
    ),
    "rebc_surge_macd": (
        "一买之后的强势阳线。此前有 MACD 口径的 rebc 一买；前一根 MA5 还不超过 MA10，收盘至少在一条短均线之下，"
        "当天振幅或相对前收超过约 6%，而这根 K 线的涨幅要超过一买以来任何一根的涨幅。"
        "买的是背驰之后第一根真正放大的阳线。"
    ),
    "rebc_surge_ma5ma10": (
        "一买之后的强势阳线，一买来自 MA5/MA10 口径的 rebc。前一根短均线仍空头、收盘还在均线压力下，"
        "当天波动超过约 6%，涨幅超过一买以来的单根最大涨幅。思想与 rebc_surge_macd 相同。"
    ),
    "seg_surge": (
        "新低之后的左侧买点，在死叉当天用下影线承接。处在强势区：MA5 仍低于 MA10，但 DIF 和 DEA 在零轴上方，"
        "当天 MACD 死叉并收长下影。最近上涨段的涨幅至少是前一段的两倍，回调以来的 MA5 不碰到前一段 MA5 的高点，"
        "前一个下跌段还是近三段下跌里最低的。不等反弹幅度被确认，在恐慌下影处买入。"
    ),
    "surge_ma": (
        "同一天收盘从 MA5 和 MA10 下方同时站上两条均线，并且当天接近涨停，或者成交量达到 5 日均量的数倍。"
        "日线还要看到最近一段 MACD 上涨的柱体峰值明显大于前一段，用来确认多头动能在加速。"
        "站上双均线只是形态，涨停或放量才是这根 K 线被选中的原因。"
    ),
    "up_trend": (
        "用 MACD 红波判断上涨还没有走完。最近一个红波的面积至少是前一个红波的两倍；"
        "前一个红波内部出现过柱子缩小再放大，最近这个红波没有这种走弱。"
        "当前 MACD 仍在零轴下，但已经比前一根大。买的是趋势中的回踩，而不是红波已经结束之后。"
    ),
    "xd_surge": (
        "阶段新低之后的右侧确认。阶段高点之后出现两到三段下跌，最近这段下跌的低点是高点以来的最低点。"
        "当天从这个低点反弹的幅度，要超过历史上从同一低点走出的最大涨幅，同时站上 MA60、当天涨幅至少 2%、"
        "长均线向上、量能放大，但还没有突破前高。与 seg_surge 共用新低后的反弹框架，这里等反弹力度被确认再买。"
    ),
    "xianren": (
        "上升趋势里的仙人指路。一根小实体、长上影的 K 线，上影大约是实体的两到三倍，并且成交量放大，"
        "出现在上涨的初期或中段。后面的 K 线要突破这根上影线的高点，形态才算确认。"
        "长上影本身是试探，突破上影高点才是买入依据。"
    ),
    "yd": (
        "指数弱的时候买更强的个股。对照指数收在自己的 MA5 和 MA10 之下，短均线还是空头；"
        "个股当天涨幅至少比指数高出 2 个点，成交量超过 5 日均量的 1.6 倍，收盘上穿 MA60 或其他长均线。"
        "代码里的信号名是 yd_ma，案例里记为 yd。买的是指数走弱背景下的逆势上穿。"
    ),
}


def conn_str() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    secrets = REPO / ".streamlit" / "secrets.toml"
    if not secrets.exists():
        secrets = Path("/home/lei/volumes/signalview/secrets.toml")
    if not secrets.exists():
        return None
    import tomllib

    data = tomllib.loads(secrets.read_text(encoding="utf-8"))
    return data.get("connections", {}).get("quantdb", {}).get("url")


def main() -> int:
    url = conn_str()
    if not url:
        print("未配置 PG 连接")
        return 2
    import psycopg

    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT to_regclass('public.signal_lab_case')::text, "
            "to_regclass('public.strategy_case')::text"
        )
        old_name, new_name = cur.fetchone()
        old_kind = None
        if old_name:
            cur.execute(
                "SELECT relkind FROM pg_class WHERE oid = 'public.signal_lab_case'::regclass"
            )
            old_kind = cur.fetchone()[0]
        if old_kind == "r" and new_name is None:
            cur.execute("ALTER TABLE signal_lab_case RENAME TO strategy_case")
            cur.execute(
                "ALTER TABLE strategy_case RENAME CONSTRAINT signal_lab_case_pkey "
                "TO strategy_case_pkey"
            )
            cur.execute(
                "ALTER INDEX idx_signal_lab_case_date RENAME TO idx_strategy_case_date"
            )
        elif new_name is None:
            raise SystemExit("strategy_case 不存在，且没有可改名的 signal_lab_case 表")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy (
                name        text PRIMARY KEY,
                core_idea   text NOT NULL DEFAULT '',
                created_at  timestamptz NOT NULL DEFAULT now(),
                updated_at  timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT ck_strategy_name_nonempty CHECK (btrim(name) <> '')
            )
            """
        )
        cur.execute(
            """
            COMMENT ON TABLE strategy IS '策略说明，一行一个策略';
            COMMENT ON COLUMN strategy.name IS '策略名，与 strategy_case.strategy 相同';
            COMMENT ON COLUMN strategy.core_idea IS '策略核心思想';
            COMMENT ON TABLE strategy_case IS '策略案例';
            COMMENT ON COLUMN strategy_case.strategy IS '策略名，对应 strategy.name';
            """
        )
        cur.executemany(
            """
            INSERT INTO strategy (name, core_idea)
            VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET
                core_idea = EXCLUDED.core_idea,
                updated_at = now()
            """,
            list(CORE_IDEAS.items()),
        )
        cur.execute(
            """
            SELECT strategy FROM strategy_case
            WHERE btrim(strategy) <> ''
            GROUP BY strategy
            HAVING strategy NOT IN (SELECT name FROM strategy)
            """
        )
        missing = [r[0] for r in cur.fetchall()]
        if missing:
            conn.rollback()
            print("案例中的策略没有核心思想，已回滚：", ", ".join(missing))
            return 1
        # 简单视图，已部署进程仍按旧表名查询
        cur.execute("DROP VIEW IF EXISTS signal_lab_case")
        cur.execute(
            """
            CREATE VIEW signal_lab_case AS
            SELECT id, name, signal_date, symbol_id, signal, strategy, info, note,
                   created_at, updated_at
            FROM strategy_case
            """
        )
        cur.execute("SELECT count(*) FROM strategy")
        n_strategy = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM strategy_case")
        n_case = cur.fetchone()[0]
        conn.commit()
    print(f"完成：strategy {n_strategy} 行，strategy_case {n_case} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
