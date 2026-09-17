# ติดตั้งตัวอัปเดต Codex Desktop Personal

> **ยังไม่เปิดใช้งาน:** candidate 2.2.0 ยังไม่มี protected release และ pilot จริง เอกสารนี้ใช้หลังผู้ดูแลส่ง ZIP updater ที่ตรวจ checksum แล้วเท่านั้น นี่คือ **team-managed auto-update ไม่ใช่ native Codex auto-update** และไม่รับรอง CLI/IDE เป็น work surface

## ก่อนติดตั้ง

ต้องใช้ macOS หรือ Windows, Python 3.11+, Git, Codex Desktop บัญชี Personal และ Codex client ที่ capability probe รองรับ ติดตั้งต่อผู้ใช้ OS/เครื่อง; เปลี่ยนเครื่องหรือเปลี่ยนผู้ใช้ OS ต้องติดตั้งใหม่ ข้อมูล local นี้ไม่แยกตามบัญชี Codex และไม่หายอัตโนมัติเมื่อสลับ Workspace. company Workspace rollout พักไว้

ผู้ดูแลต้องเผยแพร่ release จาก `Suppacha/team-engineering-skills-plugin` ช่อง `stable` ผ่าน protection/approval จริงก่อน ห้ามใช้ `main` หรือ feature branch แทน และห้ามเขียนทับ version ที่เคยเผยแพร่

## ติดตั้ง

1. ตรวจ SHA-256 ของ ZIP updater ตามประกาศ release แล้วแตกไฟล์ไป directory ที่ผู้ใช้ OS คนนี้ควบคุม เปิด Terminal/PowerShell ที่ root ของไฟล์ที่แตก
2. หา absolute path จาก `PATH` ที่ผู้ใช้คนนี้ตั้งไว้ แล้วส่งให้ installer อย่างชัดเจน; หากหาไม่พบให้ติดตั้ง prerequisite หรือถามผู้ดูแล ห้ามเดา path:

   macOS:

   ```sh
   CODEX_BIN="$(command -v codex)" && GIT_BIN="$(command -v git)" && \
     sh ./scripts/install-updater.command --codex "$CODEX_BIN" --git "$GIT_BIN"
   ```

   Windows PowerShell:

   ```powershell
   $codexBin = (Get-Command codex -ErrorAction Stop).Source
   $gitBin = (Get-Command git -ErrorAction Stop).Source
   & .\scripts\install-updater.ps1 --codex $codexBin --git $gitBin
   ```

   ใช้ `sh` ตามตัวอย่างเพราะ ZIP แบบ portable ไม่รับประกัน executable bit ของ wrapper ใช้สิทธิ์ผู้ใช้ปกติ ไม่ใช้ root, Run as administrator หรือ highest privileges Wrapper ไม่ค้นหา Codex/Git เองและไม่รองรับการ double-click โดยไม่มี arguments
3. อ่าน source, plugin และตำแหน่ง scheduler ที่ installer แสดง หากพบ marketplace/plugin ชื่อซ้ำจาก ZIP/local/Git เดิม ให้หยุดและขอ migration จากผู้ดูแล
4. initial check ต้องสำเร็จก่อน scheduler จึงเปิด: macOS ใช้ user LaunchAgent; Windows ใช้ Task Scheduler แบบ `InteractiveToken`/least privilege
5. refresh/restart Codex Desktop และเปิดแชตใหม่เพื่อพิสูจน์ loaded evidence

ตัวอัปเดตตรวจเมื่อ logon และทุก 4 ชั่วโมง เครื่องหลับ ปิด หรือ offline ทำให้รอบเลื่อนได้; เมื่อ session/network กลับมาจึงตรวจใหม่ โดยคง previous verified package ไว้เมื่อ update ล้มเหลว

## ใช้งานและตรวจสถานะ

เมื่อสำเร็จ installer พิมพ์ `management-command=... status ...` ที่มี Python, installed immutable entry point และ state directory ครบ ให้เก็บคำสั่งนี้ไว้เฉพาะเครื่อง แล้วเปลี่ยน `status` ท้ายคำสั่งเป็น `check`, `pause`, `resume` หรือ `uninstall-updater` ตามงาน `check` ใช้ gate เดียวกับ scheduler ไม่ bypass approval

- `status`: อ่าน enabled/paused, installed version/SHA, last check/result, available verified version และ reload-required
- `pause`: ปิดเฉพาะ scheduler ของทีม
- `resume`: เปิดหลังตรวจ source/capability; ถ้า `repair-required` ต้องซ่อมก่อน
- `uninstall-updater`: ถอนเฉพาะ scheduler และปิด updater; ไม่ลบ plugin, previous package, backup หรือ project files

Installed version ไม่พิสูจน์ session เดิม ให้ refresh/restart และเปิดแชตใหม่เสมอ Log อยู่ในเครื่องเท่านั้น เป็น metadata จำกัดไม่เกิน 5 ไฟล์ ไฟล์ละ 1 MiB ไม่มี telemetry, prompt, credential หรือ path งาน

Updater runtime ไม่ self-update จาก plugin package หาก protocol/runtime เปลี่ยน ผู้ดูแลต้องแจก updater ZIP ใหม่แยกต่างหาก ดูขั้นตอน `repair-required`, duplicate source และการเก็บ previous package ใน [ภาคผนวกผู้ดูแล](MAINTAINER_APPENDIX_TH.md)
