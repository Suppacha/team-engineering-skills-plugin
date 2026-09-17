# แบบบันทึก pilot native auto-update

> สถานะเริ่มต้นทั้งหมดคือ **NOT RUN**. เอกสารนี้ไม่ใช่ telemetry uploader และไม่ส่งข้อมูลออกอัตโนมัติ ผู้ทดสอบบันทึกเฉพาะข้อมูลสังเคราะห์/หลักฐานที่องค์กรอนุญาต ห้ามใส่ secret, prompt จริง, BA/customer material หรือข้อมูลส่วนบุคคล

ทดสอบ A → B ที่ version ต่างกันในกลุ่มจำกัด หลัง Admin configuration จริง บันทึกหลักฐาน installed และ loaded แยกกัน การมี package บนดิสก์หรือ sync report ไม่พิสูจน์ว่า session โหลดแล้ว

| Client / channel | OS | Version A | Version B | SHA/source | account scope | automatic check observation | installed evidence | loaded evidence | session/reload time | Result | limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Codex / company Workspace | macOS | — | — | — | — | — | — | — | — | NOT RUN | — |
| Codex / company Workspace | Windows | — | — | — | — | — | — | — | — | NOT RUN | — |
| Claude Code / stable Git marketplace | macOS | — | — | — | — | — | — | — | — | NOT RUN | — |
| Claude Code / stable Git marketplace | Windows | — | — | — | — | — | — | — | — | NOT RUN | — |

## วิธีบันทึกต่อแถว

1. ระบุ client version/OS จริง, Version A/B ของ package, full released SHA และ source/ref `stable`.
2. ระบุ account scope: company Workspace/member สำหรับ Codex หรือเครื่อง+ผู้ใช้ OS/user scope สำหรับ Claude Code
3. ติดตั้ง A แล้วเก็บ installed evidence; เปิด session และเก็บ loaded evidence จากแหล่งที่ตรวจย้อนกลับได้
4. เผยแพร่ B ตาม gate แล้วสังเกต automatic check: Codex ต้องมีรอบ daily sync ที่ไม่กด Sync now; Claude Code ต้องไม่สั่ง manual update และรอ startup check ตามช่วงที่บันทึก
5. บันทึกเวลารอ, เวลา session/reload, วิธี reload และ limitation; หากหลักฐานใดขาดให้คง NOT RUN หรือระบุผลล้มเหลวตามข้อเท็จจริง ห้ามเดา

หลังครบทั้งสี่แถว Admin จึงประเมิน compatibility/rollout แยกต่างหาก ผลจาก OS/client หนึ่งห้ามใช้แทนอีกคู่
