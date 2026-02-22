import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'C:\Users\PRO\Desktop\CUDA\synclub-local\frontend\src\app\create\page.tsx'
content = open(path, encoding='utf-8-sig').read()

# Fix encoding issues: replace garbled emoji bytes
content = content.replace('\u00e9\u0154\u0107\u011b\u015b', '\U0001f4f7')
content = content.replace('\u010d\u017eŻ', '\u00b7')

# Add t = useT() to AvatarUploader
old = 'function AvatarUploader({ value, onChange }: { value: string; onChange: (url: string) => void }) {\n  const [uploading,'
new = 'function AvatarUploader({ value, onChange }: { value: string; onChange: (url: string) => void }) {\n  const t = useT();\n  const [uploading,'
content = content.replace(old, new)

# Add t = useT() to CreatePage
old2 = 'export default function CreatePage() {\n  const router = useRouter();'
new2 = 'export default function CreatePage() {\n  const router = useRouter();\n  const t = useT();'
content = content.replace(old2, new2)

# Replace hardcoded upload error strings
replacements = [
    ('setUploadError("Please select an image file.");', 'setUploadError(t.create.uploaderInvalidType);'),
    ('setUploadError("Image must be under 10 MB.");', 'setUploadError(t.create.uploaderTooLarge);'),
    ('throw new Error(err.detail || "Upload failed")', 'throw new Error(err.detail || t.create.uploaderFailed)'),
    ('setUploadError(e instanceof Error ? e.message : "Upload failed")', 'setUploadError(e instanceof Error ? e.message : t.create.uploaderFailed)'),
    ('>Click to change</span>', '>{t.create.uploaderChange}</span>'),
    ('>Uploading...</span>', '>{t.create.uploaderUploading}</span>'),
    ('>Click or drag &amp; drop to upload</p>', '>{t.create.uploaderClick}</p>'),
    ('>JPG \u00b7 PNG \u00b7 GIF \u00b7 WEBP \u00b7 Max 10 MB</p>', '>{t.create.uploaderFormats}</p>'),
    ('>Or paste an image (Ctrl+V)</p>', '>{t.create.uploaderPaste}</p>'),
    ('>or enter URL</span>', '>{t.create.uploaderOrUrl}</span>'),
    ('placeholder="https://... or /avatars/example.png"', 'placeholder={t.create.uploaderUrlPlaceholder}'),
    ('>Remove image\n        </button>', '>{t.create.uploaderRemove}\n        </button>'),
    # CreatePage form
    ('setError("Name and Character Definition are required")', 'setError(t.create.errorRequired)'),
    ('setError(err instanceof Error ? err.message : "Failed to create character")', 'setError(err instanceof Error ? err.message : t.create.errorFailed)'),
    ('{loading ? "Creating..." : "Create & Start Chat"}', '{loading ? t.create.submitting : t.create.submit}'),
    # Page labels
    ('<span className="gradient-text">Create AI Character</span>', '<span className="gradient-text">{t.create.title}</span>'),
    # Avatar label
    ('>Avatar</label>', '>{t.create.avatar}</label>'),
    ('>Name <span', '>{t.create.name} <span'),
    ('>Tagline</label>', '>{t.create.tagline}</label>'),
    ('placeholder="e.g., Sakura, Lord Viktor"', 'placeholder={t.create.namePlaceholder}'),
    ('placeholder="Short hook shown on the character card"', 'placeholder={t.create.taglinePlaceholder}'),
    ('>Character Definition <span', '>{t.create.definition} <span'),
    ('>Opening Message</label>', '>{t.create.openingMessage}</label>'),
    ('>Category</label>', '>{t.create.category}</label>'),
    ('>Tags</label>', '>{t.create.tags}</label>'),
    ('placeholder="Romance,NSFW,Fantasy"', 'placeholder={t.create.tagsPlaceholder}'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f'[OK] {old[:60]}')
    else:
        print(f'[--] Not found: {old[:60]}')

open(path, 'w', encoding='utf-8').write(content)
print('\nDone! File written.')
