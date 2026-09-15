"use client";

import { useState, useEffect } from "react";
import { Monitor } from "lucide-react";

interface Props {
  hostId: number;
  /** ISO-время последнего снимка. null/undefined — снимка ещё нет, показываем
   *  заглушку. Значение меняется при новом снимке → пересобирается src → браузер
   *  перезапрашивает картинку (живое обновление без ручного refetch). */
  capturedAt?: string | null;
  /** Классы размера контейнера (соотношение 16:9, напр. "w-40 h-[90px]"). */
  className?: string;
  /** Размер иконки-заглушки. */
  iconSize?: number;
}

/**
 * Миниатюра рабочего стола хоста. Лениво подгружает JPEG с
 * `/api/python/api/hosts/{id}/screenshot`, поверх заглушки, с плавным
 * появлением (fade). Куки-аутентификация уходит автоматически (same-origin
 * <img>). Пока снимка нет / ошибка / загрузка — видна заглушка с иконкой.
 */
export function HostScreenshot({ hostId, capturedAt, className = "", iconSize = 20 }: Props) {
  const [loaded, setLoaded] = useState(false);
  const [errored, setErrored] = useState(false);

  // Новый снимок (сменился capturedAt) — сбрасываем состояние, чтобы снова
  // проиграть fade и не показывать старую картинку как «уже загруженную».
  useEffect(() => {
    setLoaded(false);
    setErrored(false);
  }, [capturedAt]);

  const showImage = Boolean(capturedAt) && !errored;
  const src = capturedAt
    ? `/api/python/api/hosts/${hostId}/screenshot?t=${encodeURIComponent(capturedAt)}`
    : "";

  return (
    <div
      className={`relative overflow-hidden rounded-[10px] bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shrink-0 ${className}`}
    >
      {/* Заглушка — иконка монитора; гаснет, когда картинка загрузилась. */}
      <div
        className={`absolute inset-0 flex items-center justify-center text-gray-400 transition-opacity duration-500 ${
          loaded && showImage ? "opacity-0" : "opacity-100"
        }`}
      >
        <Monitor size={iconSize} />
      </div>
      {showImage && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt="Экран рабочего стола"
          loading="lazy"
          draggable={false}
          onLoad={() => setLoaded(true)}
          onError={() => setErrored(true)}
          className={`w-full h-full object-cover transition-opacity duration-500 ${
            loaded ? "opacity-100" : "opacity-0"
          }`}
        />
      )}
    </div>
  );
}
