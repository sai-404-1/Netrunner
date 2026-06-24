from __future__ import annotations

from .base import BaseRepository, utcnow_iso
from ..models.board import Board


class BoardRepo(BaseRepository):
    model_cls = Board

    def by_owner(self, user_id: int) -> list[Board]:
        return self.filter(owner_user_id=user_id)

    def all_boards(self) -> list[Board]:
        return self.all(order_by='id')

    def create_board(self, name: str, owner_user_id: int, width: int = 1600, height: int = 900) -> Board:
        now = utcnow_iso()
        return self.create(
            name=name,
            owner_user_id=owner_user_id,
            width=width,
            height=height,
            created_at=now,
            updated_at=now,
        )

    def get_with_hosts(self, board_id: int) -> dict | None:
        board = self.get(board_id)
        if board is None:
            return None
        rows = self.conn.execute(
            """SELECT bh.host_id, bh.x, bh.y, h.name, h.address, h.is_active
               FROM board_hosts bh
               JOIN hosts h ON h.id = bh.host_id
               WHERE bh.board_id = ?
               ORDER BY bh.id""",
            (board_id,),
        ).fetchall()
        placements = [
            {"host_id": r["host_id"], "x": r["x"], "y": r["y"],
             "name": r["name"], "address": r["address"], "is_active": r["is_active"]}
            for r in rows
        ]
        return {"board": board, "placements": placements}

    def save_layout(self, board_id: int, positions: list[dict]) -> None:
        self.conn.execute("DELETE FROM board_hosts WHERE board_id = ?", (board_id,))
        for pos in positions:
            self.conn.execute(
                "INSERT INTO board_hosts (board_id, host_id, x, y) VALUES (?, ?, ?, ?)",
                (board_id, pos["host_id"], pos.get("x", 0), pos.get("y", 0)),
            )
        self.conn.execute(
            "UPDATE boards SET updated_at = ? WHERE id = ?",
            (utcnow_iso(), board_id),
        )
        self.conn.commit()
