import { notFound } from 'next/navigation'
import { ContentPage, DocumentContent } from '@/components/content'
import { getPage, getService, getTeam } from '@/lib/content'

export const dynamic = 'force-dynamic'

export default async function Detail({ params }: { params: Promise<{ section: string; item: string }> }) {
  const { section, item } = await params
  if (section === 'services') {
    const service = await getService(item)
    if (!service) notFound()
    return <ContentPage title={service.title}>{service.comingSoon && <span className="badge">به‌زودی</span>}<DocumentContent content={service.content} />{service.cta && <button className="button" type="button" disabled>{service.cta}</button>}</ContentPage>
  }
  if (section === 'company' && item === 'about') {
    const page = await getPage('about')
    if (!page) notFound()
    return <ContentPage title={page.title}><DocumentContent content={page.content} /></ContentPage>
  }
  if (section === 'company' && item === 'team') {
    const members = await getTeam()
    return <ContentPage title="تیم">{members.map((member) => <article key={member.id}><h2>{member.name}</h2>{member.biography && <p>{member.biography}</p>}</article>)}</ContentPage>
  }
  notFound()
}
