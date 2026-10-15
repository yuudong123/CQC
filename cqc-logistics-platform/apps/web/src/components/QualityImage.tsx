"use client";

import Image from "next/image";
import { useState } from "react";

/** 서버 미리보기는 만료될 수 있어 실패하면 안내 문구로 바꾼다. 관제·관리자 화면이 같이 쓴다. */
export default function QualityImage({
  src,
  alt,
  remote,
}: {
  src?: string;
  alt: string;
  remote: boolean;
}) {
  const [failed, setFailed] = useState(false);
  return !src || failed ? (
    <p className="qc-muted">이미지 조회 불가 · 만료 또는 연결 끊김</p>
  ) : (
    <Image
      src={src}
      alt={alt}
      fill
      sizes="(max-width:650px) 40vw, 500px"
      loading="eager"
      unoptimized={remote}
      onError={() => setFailed(true)}
    />
  );
}
