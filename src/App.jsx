import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";
import ScrollToAnchor from "@/components/ScrollToAnchor";
import Dashboard from "@/components/Dashboard";
import InvestmentForm from "@/components/InvestmentForm";
import RecordsList from "@/components/RecordsList";
import Analytics from "@/components/Analytics";
import Settings from "@/components/Settings";
import ImageLibrary from "@/components/ImageLibrary";

function App() {
  return (
    <Router>
      <ScrollToAnchor />
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Navigation />
        <main className="flex-grow container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/add-record" element={<InvestmentForm />} />
            <Route path="/records" element={<RecordsList />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/images" element={<ImageLibrary />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </Router>
  );
}

export default App;
