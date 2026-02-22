import Link from "next/link";

export default function Footer() {
  return (
    <footer>
      <div>
        <div>
          <div>
            <h3>Sustain</h3>
          </div>
          <div>
            <h4>Legal</h4>
            <ul>
              <li><Link href="/privacy-policy">Privacy Policy</Link></li>
              <li><Link href="/tos">Terms of Service</Link></li>
            </ul>
          </div>
        </div>
        <div>
          <p>© 2024 Sustain. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
