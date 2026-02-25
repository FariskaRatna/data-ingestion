for match in re.finditer(r'dakwaan', self.text, re.IGNORECASE):
    start = max(0, match.start() - 150)
    end = match.end() + 150
    window = self.text[start:end].lower()
    
    model_match = re.search(
        r'(tunggal|alternatif|kumulatif|subsider|subsidair)',
        window
    )
    
    if model_match:
        model = model_match.group(1)
        self._add_field("what", "indictment_model", model, 0.97)
        self.log(f"  ✅ Indictment Model (window): {model}")
        break