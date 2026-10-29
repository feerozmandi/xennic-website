import Link from 'next/link'

export default function Home() {
  return <>
    <section className="hero"><div className="container hero-content">
      <p className="eyebrow">زر نور نیرو یکتا | Xennic</p>
      <h1>وب‌سایت Xennic</h1>
      <p>ساختار اولیهٔ وب‌سایت؛ محتوا پس از تأیید ساختار افزوده می‌شود.</p>
      <Link className="button" href="/services">خدمات</Link>
    </div></section>
    <section className="container page"><h2>بخش‌های وب‌سایت</h2>
      <div className="cards">
        {[['/company', 'شرکت'], ['/services', 'خدمات'], ['/track-record', 'پیشینهٔ مهندسی'], ['/contact', 'تماس با ما']].map(([href, label]) => <Link className="card" href={href} key={href}><h3>{label}</h3><span>مشاهدهٔ ساختار صفحه ←</span></Link>)}
      </div>
    </section>
  </>
}
