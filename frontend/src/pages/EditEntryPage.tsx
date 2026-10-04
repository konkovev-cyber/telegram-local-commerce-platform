import { useNavigate } from 'react-router-dom'
import EntryEditor from '../components/EntryEditor'

export default function EditEntryPage() {
  const navigate = useNavigate()
  return <EntryEditor onBack={() => navigate(-1)} />
}
