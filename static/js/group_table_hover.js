document.addEventListener("mouseover", function(e) {
  const row = e.target.closest("tr[data-group-id]");
  if (!row) return;

  const groupId = row.dataset.groupId;
  const groupRows = document.querySelectorAll(`tr[data-group-id="${groupId}"]`);

  groupRows.forEach(r => {
    r.classList.add("highlight");
    r.classList.remove("group-last");
  });

  if (groupRows.length) {
    groupRows[groupRows.length - 1].classList.add("group-last");
  }
});

document.addEventListener("mouseout", function(e) {
  const fromRow = e.target.closest("tr[data-group-id]");
  const toRow = e.relatedTarget?.closest("tr[data-group-id]");

  // если мы всё ещё внутри той же строки/группы — игнорим
  if (fromRow && toRow && fromRow.dataset.groupId === toRow.dataset.groupId) {
    return;
  }

  if (!fromRow) return;

  const groupId = fromRow.dataset.groupId;
  const groupRows = document.querySelectorAll(`tr[data-group-id="${groupId}"]`);

  groupRows.forEach(r => {
    r.classList.remove("highlight", "group-last");
  });
});