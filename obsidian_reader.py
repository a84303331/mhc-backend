"""MHC Backend — Obsidian Vault Reader

讀取本地 Obsidian vault 中的 MHC 知識庫檔案。
提供 HC 清單、案例庫、偏誤對照表的結構化讀取。
"""

import os
from pathlib import Path
from typing import Optional


class ObsidianReader:
    """讀取 Obsidian vault 中的 MHC 相關檔案"""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.mhc_dir = self.vault_path / "1_Projects" / "minerva-hc-toolbox"
        self.hbb_dir = self.vault_path / "1_Projects" / "human-behavioral-bias-toolbox"

    @property
    def is_accessible(self) -> bool:
        """檢查 vault 是否可訪問"""
        return self.vault_path.exists()

    def read_file(self, relative_path: str) -> Optional[str]:
        """讀取 vault 中的檔案"""
        full_path = self.vault_path / relative_path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        return None

    def get_hc_master_list(self) -> Optional[str]:
        """讀取 HC 完整清單"""
        return self.read_file("1_Projects/minerva-hc-toolbox/01-hc-master-list.md")

    def get_hc_detailed_guide(self) -> Optional[str]:
        """讀取 11 HC 官方詳細說明"""
        return self.read_file("1_Projects/minerva-hc-toolbox/02-hc-detailed-guide.md")

    def get_hc_application_matrix(self) -> Optional[str]:
        """讀取情境匹配矩陣"""
        return self.read_file("1_Projects/minerva-hc-toolbox/03-hc-application-matrix.md")

    def get_hc_supplement(self) -> Optional[str]:
        """讀取學術補充知識庫"""
        return self.read_file("1_Projects/minerva-hc-toolbox/06-hc-supplement.md")

    def get_bias_hc_mapping(self) -> Optional[str]:
        """讀取偏誤↔HC 映射表"""
        return self.read_file("1_Projects/human-behavioral-bias-toolbox/04-bias-hc-mapping.md")

    def list_case_files(self, limit: int = 20) -> list[str]:
        """列出案例 MD 檔案（用於 few-shot）"""
        case_dir = self.mhc_dir / "案例 MD"
        if not case_dir.exists():
            return []
        files = sorted(
            [f for f in case_dir.glob("*.md") if f.name != "!index.md"],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        return [str(f.relative_to(self.vault_path)) for f in files[:limit]]

    def get_case_content(self, case_path: str) -> Optional[str]:
        """讀取單一案例內容"""
        return self.read_file(case_path)

    def get_recent_cases_text(self, max_cases: int = 3, max_chars: int = 3000) -> str:
        """取得最近案例的摘要文字（用於注入 prompt）"""
        case_files = self.list_case_files(limit=max_cases)
        texts = []
        total_chars = 0
        for cf in case_files:
            content = self.get_case_content(cf)
            if not content:
                continue
            # 取前 1000 字作為摘要
            summary = content[:1000]
            texts.append(f"### 案例：{Path(cf).stem}\n{summary}\n")
            total_chars += len(summary)
            if total_chars > max_chars:
                break
        return "\n".join(texts)

    def health_check(self) -> dict:
        """健康檢查：回傳各檔案讀取狀態"""
        checks = {
            "vault_accessible": self.is_accessible,
            "hc_master_list": bool(self.get_hc_master_list()),
            "hc_detailed_guide": bool(self.get_hc_detailed_guide()),
            "hc_application_matrix": bool(self.get_hc_application_matrix()),
            "bias_hc_mapping": bool(self.get_bias_hc_mapping()),
            "case_count": len(self.list_case_files()),
        }
        return checks
