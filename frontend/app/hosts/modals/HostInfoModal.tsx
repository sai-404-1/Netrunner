"use client";

import {Modal} from "@/components/Modal";
import {formatDate} from "@/lib/utils";
import {RefreshCw, TerminalSquare, KeyRound, Pencil, Trash2} from "lucide-react";
import type {Host} from "@/lib/host-types";

interface Props {
  host: Host;
  canTerminal: boolean;
  onClose: () => void;
  onCheck: (host: Host) => void;
  onTerminal: (host: Host) => void;
  onReprovision: (host: Host) => void;
  onEdit: (host: Host) => void;
  onDelete: (host: Host) => void;
}

/** Карточка с информацией о хосте + действия. Stateless, действия — колбэки наверх. */
export function HostInfoModal({host, canTerminal, onClose, onCheck, onTerminal, onReprovision, onEdit, onDelete}: Props) {
  return (
    <Modal title={host.name} onClose={onClose}>
      <div className="grid gap-4">
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div>
            <div className="text-gray-500">Пользователь</div>
            <div className="font-medium">{host.username}</div>
          </div>
          <div>
            <div className="text-gray-500">Порт</div>
            <div className="font-medium">{host.port}</div>
          </div>
          <div>
            <div className="text-gray-500">Был в сети</div>
            <div className="font-medium">{formatDate(host.last_seen) || "—"}</div>
          </div>
          <div>
            <div className="text-gray-500">Группа</div>
            <div className="font-medium">{host.group_name || "—"}</div>
          </div>
          <div className="col-span-2">
            <div className="text-gray-500">Описание</div>
            <div className="font-medium">{host.description || "—"}</div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 pt-2 border-t dark:border-gray-700">
          <button className="btn-secondary" onClick={() => onCheck(host)}>
            <RefreshCw size={15}/> Проверить
          </button>
          {canTerminal && (
            <button className="btn-secondary" onClick={() => onTerminal(host)}>
              <TerminalSquare size={15}/> Терминал
            </button>
          )}
          <button className="btn-secondary" onClick={() => onReprovision(host)}>
            <KeyRound size={15}/> Перепривязать ключ
          </button>
          <button className="btn-secondary" onClick={() => onEdit(host)}>
            <Pencil size={15}/> Редактировать
          </button>
          <button className="btn-danger" onClick={() => onDelete(host)}>
            <Trash2 size={15}/> Удалить
          </button>
        </div>
      </div>
    </Modal>
  );
}