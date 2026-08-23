"use client";

import {Modal} from "@/components/Modal";
import type {Group} from "@/lib/host-types";
import {useEffect, useState} from "react";

interface Props {
  groups: Group[];
  onClose: () => void;
  onSubmit: (fd: FormData, keyFile: File | null) => void;
  onCreateGroup: () => void;
}

/** Форма добавления хоста. Stateless: не знает про API, отдаёт FormData наверх. */
export function AddHostModal({groups, onClose, onSubmit, onCreateGroup}: Props) {
  const [nameCanGen, setNameCanGen] = useState(true);
  const [ipValue, setIpValue] = useState('');
  const [hostName, setHostName] = useState('');
  const [selectedGroup, setSelectedGroup] = useState('');

  function validateIP(ip: string): boolean {
    const ipv4Pattern = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return ipv4Pattern.test(ip);
  }

  useEffect(() => {
    const trimmedIP = ipValue.trim();
    if (selectedGroup !== "" && selectedGroup != "Без группы") {
      setHostName(selectedGroup)
    }
    if (validateIP(trimmedIP) && selectedGroup != "Без группы") {
      console.log("ip is valid");
      setHostName(`${selectedGroup}_${ipValue.split(".")[3]}`);
    }

  }, [ipValue, selectedGroup])

  return (
    <Modal title="Добавить хост" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const fileInput = e.currentTarget.querySelector<HTMLInputElement>('input[type="file"]');
          onSubmit(new FormData(e.currentTarget), fileInput?.files?.[0] || null);
        }}
        className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 items-end"
      >
        {/* TODO в контексте предметной области, зачастую юзернейм на целевом компьютере один и тот же */}
        {/* TODO потому решено в будущем организовать автоматическое подставление юзернейма в данное поле */}
        {/* данный участок кода будет вынесен в раздел, подразумевающий расширенную первичную настройку */}
        {/*<label className="label">*/}
        {/*  Пользователь*/}
        {/*  <input className="input" name="username" placeholder="admin" required/>*/}
        {/*</label>*/}

        <label className="label">
          IP-адрес
          <input className="input" name="address" placeholder="192.168.1.10"
                 onChange={(e) => setIpValue(e.target.value)}
                 required/>
        </label>

        {/* данный участок кода будет вынесен в раздел, подразумевающий расширенную первичную настройку */}
        {/*<label className="label">*/}
        {/*  Порт*/}
        {/*  <input className="input" name="port" type="number" defaultValue={22} required/>*/}
        {/*</label>*/}

        <label className="label">
          Группа
          <select className="input" name="group_id" onChange={(e) => setSelectedGroup(e.target.selectedOptions.item(0).text)}>
            <option value="">Без группы</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </select>
        </label>

        {/* TODO переработать логику. исходя из выбранной группы хосту определяется начало имени, далее после вписывания ip адреса определяется конец имени */}
        {/* TODO например: выбрана группа по имени 3928 и ip оканчивается на 95, имя соответственно будет 3928_95 */}
        <label className="label">
          Имя хоста
          <input value={hostName} className="input" name="name" placeholder="Имя в списке" onChange={(e) => setHostName(e.target.value)} required/>
        </label>

        {/* данный участок кода будет вынесен в раздел, подразумевающий расширенную первичную настройку */}
        {/*<label className="label">*/}
        {/*  SSH-ключ*/}
        {/*  <select className="input" name="ssh_key_id">*/}
        {/*    <option value="">По умолчанию</option>*/}
        {/*    {keys.map((k) => (*/}
        {/*      <option key={k.id} value={k.id}>{k.name} ({k.key_type || k.private_key_path})</option>*/}
        {/*    ))}*/}
        {/*  </select>*/}
        {/*</label>*/}

        {/* данный участок кода будет вынесен в раздел, подразумевающий расширенную первичную настройку */}
        {/*<label className="label">*/}
        {/*  Новый SSH-ключ*/}
        {/*  <input type="file" className="input py-1.5"*/}
        {/*         onChange={(e) => setNewKeyFile(e.target.files?.[0] || null)}/>*/}
        {/*</label>*/}

        {/* TODO в контексте предметной области, целевой компьютер при первичной настройке всегда имеет один конкретный пароль
            {/* TODO потому заполнением данного поля в будущем будет заниматься сервер, а не администратор */}
        {/* данный участок кода будет вынесен в раздел, подразумевающий расширенную первичную настройку */}
        {/*<label className="label">*/}
        {/*  Пароль хоста*/}
        {/*  <input className="input" name="password" type="password" placeholder="Для автокопирования SSH-ключа"/>*/}
        {/*</label>*/}
        <label className="label md:col-span-2 lg:col-span-4">
          Описание
          <textarea className="input" name="description" rows={3}/>
        </label>
        <div className="flex gap-3 md:col-span-2 lg:col-span-4 justify-between">
          <button type="button" className="btn-secondary" onClick={onCreateGroup}>Создать
            группу
          </button>
          <button className="btn" type="submit">Добавить</button>
        </div>
      </form>
    </Modal>
  );
}